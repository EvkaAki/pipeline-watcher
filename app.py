import os
import psycopg2
import kfp
from flask import Flask

app = Flask(__name__)

@app.cli.command("update-pipelines")
def update_pipelines():
    print("Starting job...")