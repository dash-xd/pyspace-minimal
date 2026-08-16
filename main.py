import requests
import os
from os import path

from flask import Flask, current_app, request, jsonify, redirect
app = current_app

from jinja2 import Environment, FileSystemLoader, select_autoescape
env = Environment(
    loader=FileSystemLoader(path.dirname(path.abspath(__file__))),
    autoescape=select_autoescape(['html', 'xml', 'htm', '.xhtml', '.svg'])
)

@app.route('/container/run')
def main():
    return "container is running", 200

from router_loader import load_router
load_router(app)
