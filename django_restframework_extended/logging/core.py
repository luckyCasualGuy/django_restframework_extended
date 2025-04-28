import threading
import uuid
import logging
import os


thread_local = threading.local()


def get_call_id():
    return getattr(thread_local, 'call_id', None)


def get_url_name():
    return getattr(thread_local, 'url_name', None)


class GenerateCallIDMiddleware:


    def __init__(self, get_response):
        self.get_response = get_response


    def __call__(self, request):
        
        response = self.get_response(request)

        if hasattr(thread_local, "url_name"):
            del thread_local.url_name

        if hasattr(thread_local, "call_id"):
            del thread_local.call_id

        return response


    def process_view(self, request, view_func, view_args, view_kwargs):
        
        resolver_match = request.resolver_match
        if resolver_match: url_name = resolver_match.url_name
        else: url_name = 'name-not-found'

        if url_name == 'name-not-found': url_name = request.path

        thread_local.url_name = str(url_name)
        thread_local.call_id = f"{uuid.uuid4()}"


class CallIDFilter(logging.Filter):


    def filter(self, record):
        record.call_id = get_call_id()
        record.url_name = get_url_name()
        return True


class RelativeFilePathFormatter(logging.Formatter):
    

    def __init__(self, base_dir, *args, **kwargs):
        self.base_dir = base_dir
        super().__init__(*args, **kwargs)


    def format(self, record):
        record.pathname = os.path.relpath(record.pathname, self.base_dir)
        return super().format(record)

