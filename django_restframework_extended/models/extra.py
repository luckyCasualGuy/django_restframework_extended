from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import json
from cryptography.fernet import Fernet, InvalidToken



class EncryptedJSONField(models.TextField):
    
    
    def __init__(self, allow_noncompliant=False, *args, **kwargs):
        self.key = settings.ENCRYPTION_KEY 
        self.cipher_suite = Fernet(self.key) 
        self.allow_noncompliant = allow_noncompliant
        super().__init__(*args, **kwargs)


    def encrypt(self, value: dict) -> str:
        """
        Encrypts dictionary to string
        dict -> string (json) -> bytes -> bytes (encrypted) -> string (utf-8 decode)
        """
        if value != None:

            if not isinstance(value, dict):
                raise ValidationError(f"expected value dict, got: {type(value)}")
            
            try:
                json_data_binaries = json.dumps(value).encode('utf-8')
                encrypted_data = self.cipher_suite.encrypt(json_data_binaries)
                return encrypted_data.decode('utf-8')

            except TypeError as err:
                raise ValidationError(f"expected value dict is not json serializable:\nerror message: {err}")

        return value
    

    def _encrypt(self, value: dict) -> str:
        try:  return self.encrypt(value)
        except ValidationError as err:
            if self.allow_noncompliant: return str(value)
            raise err

    
    def decrypt(self, value: str) -> dict:
        """
        Decrypts encoded string
        str -> bytes (utf-8 encode) -> bytes (decrypted) -> string (json) -> dict
        """

        if value != None:

            if not isinstance(value, str):
                raise ValidationError(f"expected value str, got: {type(value)}")
            
            try:
                decrypted_data = self.cipher_suite.decrypt(value.encode('utf-8'))
                return json.loads(decrypted_data.decode('utf-8'))

            except InvalidToken as err:
                raise ValidationError(f"unable to decrypt the value")
            
            except json.decoder.JSONDecodeError as err:
                raise ValidationError(f"unable to load the decrypted data")
            
        return value


    def _decrypt(self, value: dict) -> str:
        try:  return self.decrypt(value)
        except ValidationError as err:
            if self.allow_noncompliant: return {"value": value}
            raise err


    def get_prep_value(self, value): 
        return self._encrypt(value)
    

    def from_db_value(self, value, expression, connection): 
        return self._decrypt(value)
    

    def to_python(self, value): 
        return self._decrypt(value)

