from os import path

from cloud_function_app import CloudFunctionApp

app = CloudFunctionApp(root=path.dirname(path.abspath(__file__)))
main = app.build()
