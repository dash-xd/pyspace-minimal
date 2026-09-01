from os import path

from pyspace import Service

app = Service(root=path.dirname(path.abspath(__file__)))
main = app.build()
