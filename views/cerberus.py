from django.db import IntegrityError
from django.db.models.base import ModelBase
from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.exceptions import APIException, ParseError, AuthenticationFailed, MethodNotAllowed
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers

import traceback as tb, base64, re, logging, fitz
from cerberus import Validator
from io import BytesIO
from PIL import Image


# BASIC FUNCTIONALITIES USED IN VIEWS


# REQUEST VALIDATORS


class DefaultValidator(Validator):


    @staticmethod
    def load_base64_as_io(base64_str: str) -> BytesIO:
        image_data = base64.b64decode(base64_str)
        image_buffer = BytesIO(image_data)
        image_buffer.seek(0)
        return image_buffer


    def _check_with_email(self, field, value):
        
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        regex = re.compile(pattern)
        if not regex.match(value):
            self._error(field, "email pattern invalid")


    def _check_with_image_base64_pil(self, field, value):
        try:
            image_buffer = self.load_base64_as_io(value)
            image = Image.open(image_buffer)
        except Exception as err:
            self._error(field, "enable to load base64 image")


    def _check_with_pdf(self, field, value):
        try:
            pdf_buffer = self.load_base64_as_io(value)
            pdf = fitz.open(pdf_buffer)
            
            if not pdf.page_count:
                self._error(field, "pdf does not have pages")

        except Exception as err:
            self._error(field, "enable to load base64 pdf")


# BASIC API VIEW MANAGERS


class APIViewBasic(APIView):

    DEFAULT_EXCEPTION_MESSAGE = "Internal Server Error"

    ENABLE_EXCEPTION_TRACE = False

    LOGGER: logging.Logger = None

    REQUEST_VALIDATOR = Validator()

    LOG_RESPONSE_KEYS_ONLY = False

    AUTO_ADD_FOREIGN_KEY_INITIALIZATIONS_IN_REQUEST = False


    """
    Schemas
    _QUERY_SCHEMA
    _PAYLOAD_SCHEMA

    Default Schemas
    _QUERY_DEFAULT_SCHEMA
    _PAYLOAD_DEFAULT_SCHEMA
    """

    
    class RequestValidationFailed(APIException):

        def __init__(self, error_message, *args):
            super().__init__(*args)
            self.error_message = error_message
            self.status_code = 400
            self.default_detail = error_message
            self.default_code = 'RequestValidationFailed'


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.LOGGER: self.LOGGER = logging.getLogger(str(self.LOGGER))
        else: self.LOGGER = logging.getLogger("GCP")


    def request_validations(self, request: Request):
        request.query_normalized, request.payload_normalized = {}, {}
        errors = []
        for (schema_type, default_schema_type) in [("QUERY_SCHEMA", "QUERY_DEFAULT_SCHEMA"), ("PAYLOAD_SCHEMA", "PAYLOAD_DEFAULT_SCHEMA")]:
            
            attr = f"{request.method.upper()}_{schema_type}"
            default_attr = f"{request.method.upper()}_{default_schema_type}"
            
            if schema_type == "QUERY_SCHEMA": req = request.GET.dict()
            else: req = request.data
            
            default_schema = {}
            if hasattr(self, default_attr):
                default_schema = getattr(self, default_attr)

            schema = default_schema
            if hasattr(self, attr):
                schema_ = getattr(self, attr)
                schema.update(schema_)

            if not hasattr(self, default_attr) and not hasattr(self, attr):
                continue
                
            if schema:
                
                status = self.REQUEST_VALIDATOR.validate(req, schema)
                if not status:
                    errors.append({"query" if schema_type == "QUERY_SCHEMA" else "payload": self.REQUEST_VALIDATOR.errors})

                else:
                    normalized = self.REQUEST_VALIDATOR.normalized(req, schema)
                    if schema_type == "QUERY_SCHEMA": request.query_normalized = normalized
                    else: request.payload_normalized = normalized

            else: errors = ["request should be empty"]

            # elif not schema and not hasattr(self, attr) and req: errors = ["request should be empty"]

            
        if errors: raise self.RequestValidationFailed(error_message=errors)


    def initial(self, request: Request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        self.request_validations(request)

        if self.AUTO_ADD_FOREIGN_KEY_INITIALIZATIONS_IN_REQUEST and hasattr(self, "MODEL"):
            self.request_foreign_key_initializations(request, self.MODEL)


    def handle_exception(self, err: Exception):

        response, status_code = {}, 0

        if isinstance(err, ParseError):
            response = {
                "error": "Enable to parse request",
                "error_code": "RequestInvalid",
            }
            status_code = 400


        elif isinstance(err, self.RequestValidationFailed):
            response = {
                "error": err.error_message,
                "error_code": "RequestValidationFailed",
            }
            status_code = 400


        elif isinstance(err, IntegrityError):
            trace = ''.join(tb.format_exception(None, err, err.__traceback__))
            response = {
                "error": err.args[1],
                "error_code": "RequestIntegrityFailed",
            }
            status_code = 400


        elif isinstance(err, AuthenticationFailed):
            response = err.detail
            status_code = 503


        elif isinstance(err, MethodNotAllowed):
            response = {
                "error": "method is not allowed",
                "error_code": "MethodNotAllowed"
            }
            status_code = 502


        elif isinstance(err, Exception):
            response = {
                "error": self.DEFAULT_EXCEPTION_MESSAGE,
                "error_code": "InternalServerError",
            }

            trace = ''.join(tb.format_exception(None, err, err.__traceback__))
            self.LOGGER.debug(f"trace: {trace}")
            if self.ENABLE_EXCEPTION_TRACE:
                response.update({"error_trace": trace})

            status_code = 500


        if response:
            return Response(response, status=status_code)


    def finalize_response(self, request: Request, response: Response, *args, **kwargs):
        if response:
            if self.LOG_RESPONSE_KEYS_ONLY: self.LOGGER.debug(f"response: {response.data.keys()}, status: {response.status_code}")
            else:
                
                if isinstance(response.data, dict): response_data = response.data
                else: response_data = {"response": response.data}

                if len(str(response_data)) > 1000:  # Adjust the length threshold as needed
                    self.LOGGER.debug(f"response keys: {response_data.keys()}, status: {response.status_code}")
                else: self.LOGGER.debug(f"response: {response_data}, status: {response.status_code}")

        return super().finalize_response(request, response, *args, **kwargs)


    @staticmethod
    def instance_get(model: ModelBase, _id, default=None):
        if _id:
            if not model.objects.filter(id=_id).exists():
                raise ValueError(f"{model.__name__} with id: {_id} not found")
            return model.objects.get(id=_id)
        return default


    @staticmethod
    def get_foreign_key_maps_of_model(model: models.Model) -> dict:
        foreign_key_fields = {}
        for field in model._meta.get_fields():
            if isinstance(field, models.ForeignKey):
                foreign_key_fields[field.name.lower()] = field.related_model
                # foreign_key_fields[field.attname] = field.related_model
        return foreign_key_fields


    def request_foreign_key_initializations(self, request: Request, model: models.Model):
        
        foreign_key_field_maps = self.get_foreign_key_maps_of_model(model)

        for field_name, model in foreign_key_field_maps.items():

            payload = {}
            if hasattr(request, "payload_normalized") and request.payload_normalized:
                payload = request.payload_normalized
            elif hasattr(request, "query_normalized") and request.query_normalized:
                payload = request.query_normalized

            if payload:
                model: models.Model

                field_value_in_request = payload.get(field_name, "")
                if field_value_in_request:
                    if not model.objects.filter(id=field_value_in_request).exists():
                        raise ValueError(f"{field_name} with id: {field_value_in_request} not found")
                    field_name_instance = model.objects.get(id=field_value_in_request)
                    request.payload_normalized[field_name] = field_name_instance


class APIViewModelManagerBasic(APIViewBasic):

    
    MODEL: models.Model = None
    
    
    SERIALIZER: serializers.ModelSerializer = None


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not isinstance(self.MODEL, ModelBase):
            raise ValueError(f"APIViewModelManagerBasic.MODEL should be of type django.models.Model")
        
        if not isinstance(self.SERIALIZER, serializers.SerializerMetaclass):
            raise ValueError(f"APIViewModelManagerBasic.SERIALIZER should be of type rest_framework.serializers.ModelSerializer")
  

    def get(self, request: Request):

        req = request.query_normalized
        instance = self.MODEL.objects.get(**req)
        response = self.SERIALIZER(instance).data
        
        return Response(response, status=200)


    def post(self, request: Request):

        req = request.payload_normalized
        
        instance: models.Model = self.MODEL(**req)
        instance.save()
        # instance = self.MODEL.objects.create(**req)
        
        response = self.SERIALIZER(instance).data
        

        return Response(response, status=200)
    

    def put(self, request: Request):

        req_query = request.query_normalized
        req_payload = request.payload_normalized

        if not req_query:
            raise self.RequestValidationFailed(["request query empty"])
        
        if not req_payload:
            raise self.RequestValidationFailed(["request payload empty"])
        
        instance = self.MODEL.objects.get(**req_query)
        for key, value in req_payload.items():
            setattr(instance, key, value)
        instance.save()

        response = self.SERIALIZER(instance).data
        
        return Response(response, status=200)
    

    # def delete(self, request: Request):

    #     req_query = request.query_normalized

    #     if not req_query:
    #         raise self.RequestValidationFailed(["request query empty"])
        
    #     instance = self.MODEL.objects.get(**req_query)
    #     instance.delete()

    #     response = self.SERIALIZER(instance).data
    #     return Response(response, status=200)


    def handle_exception(self, err):
        
        response = {}
        if isinstance(err, self.MODEL.DoesNotExist):
            response = {
                "error": "object not found",
                "error_code": "DoesNotExist",
            }
            status_code = 404


        elif isinstance(err, self.MODEL.MultipleObjectsReturned):
            response = {
                "error": "multiple objects found",
                "error_code": "MultipleObjectsFound"
            }
            status_code = 500
        

        if response: return Response(response, status=status_code)

        return super().handle_exception(err)


class APIViewModelManagerOpenionated(APIViewModelManagerBasic):

    __ID_VALIDATION_CHECKS_NR = {"coerce": int, "type": "integer", "required": False, "min": 0}
    __ID_VALIDATION_CHECKS_R = {"coerce": int, "type": "integer", "required": True, "min": 0}
    __ID_VALIDATION_NR = {"id": __ID_VALIDATION_CHECKS_NR}
    __ID_VALIDATION_R = {"id": __ID_VALIDATION_CHECKS_R}
    

    def get_foreign_key_validations(self) -> dict:
        foreign_key_field_maps = self.get_foreign_key_maps_of_model(self.MODEL)
        return {
            field_name: self.__ID_VALIDATION_CHECKS_R for field_name, _ in foreign_key_field_maps.items()
        }
    

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__FOREIGN_KEY_VALIDATIONS = self.get_foreign_key_validations()

        self.GET_QUERY_DEFAULT_SCHEMA = {**self.__ID_VALIDATION_NR}

        self.POST_PAYLOAD_DEFAULT_SCHEMA = {**self.__FOREIGN_KEY_VALIDATIONS}

        self.PUT_QUERY_DEFAULT_SCHEMA = {**self.__ID_VALIDATION_R}
        self.PUT_PAYLOAD_DEFAULT_SCHEMA = {}


    def handle_exception(self, err):

        response = {}
        if isinstance(err, ValueError):
            trace = ''.join(tb.format_exception(None, err, err.__traceback__))
            self.LOGGER.debug(f"ValueError trace: {trace}")
            response = {
                "error": str(err),
                "error_code": "InvalidRequest",
            }
            status_code = 400

        if response: return Response(response, status=status_code)

        return super().handle_exception(err)


class BasicPaginator(PageNumberPagination):
    page_size = 25
    page_query_param = 'page_number'
    page_size_query_param = 'page_size'
    max_page_size = 50


class APIViewModelList(APIViewBasic):


    PAGINATOR = BasicPaginator()



    MODEL: models.Model = None
    
    
    SERIALIZER: serializers.ModelSerializer = None


    ORDER_BY = []

    
    def get(self, request: Request):
        
        filters = request.query_normalized.copy()
        if self.PAGINATOR:
            filters.pop(self.PAGINATOR.page_query_param, None)
            filters.pop(self.PAGINATOR.page_size_query_param, None)

        instances = self.MODEL.objects.filter(**filters)

        if self.ORDER_BY: instances = instances.order_by(**self.ORDER_BY)

        if self.PAGINATOR:
            instances = self.PAGINATOR.paginate_queryset(instances, request)

        response = self.SERIALIZER(instances, many=True).data
        
        if self.PAGINATOR:
            print(response)
            response = self.PAGINATOR.get_paginated_response(response)
            print(response)
            return response


        return Response(response, status=200)

