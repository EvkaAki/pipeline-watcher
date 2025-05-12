import os
import psycopg2
import kfp
from flask import Flask
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

app = Flask(__name__)

def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("No DATABASE_URL set")
        return None
    try:
        conn = psycopg2.connect(dsn=db_url.replace("psql://", "postgresql://"))
        return conn
    except Exception as e:
        print("PostgreSQL error:", e)
        return None

def get_admin_client():
    try:
        token_path = os.getenv("KF_PIPELINES_SA_TOKEN_PATH")
        with open(token_path, "r") as f:
            token = f.read()
        return kfp.Client(
            host="http://ml-pipeline.kubeflow.svc.cluster.local:8888",
            client_id="admin",
            existing_token=token
        )
    except Exception as e:
        print("KFP admin client error:", e)
        return None

def check_output_artefact(path):
    s3 = boto3.client(
        's3',
        endpoint_url='http://minio-service.kubeflow.svc.cluster.local:9000',
        aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'),
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name='us-east-1'
    )

    bucket = 'artifacts'
    try:
        s3.head_object(Bucket=bucket, Key=path)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] in ['404', 'NoSuchKey']:
            return False
        raise

@app.cli.command("update-pipelines")
def update_pipelines():
    print("Starting job...")

    client = get_admin_client()
    conn = get_db_connection()
    if client and conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, run_id FROM app_runrequest WHERE state = 2;")
            rows = cur.fetchall()
            print("RunRequests with state=2:")
            for id, run_id in rows:
                print(f"Request ID: {id}, Run ID: {run_id}")
                try:
                    run = client.get_run(run_id)
                    result_url = f"{run_id}/mock-model/model_path.signed.zip"
                    print(f"Run state: {run.state} — name: {run.display_name} — run_id: {run_id}")
                    if run.state == "SUCCEEDED":
                        result_exists = check_output_artefact(result_url)
                        if not result_exists:
                            cur.execute("UPDATE app_runrequest SET result = %s WHERE id = %s;", ('None', id,))
                        else:
                            cur.execute("UPDATE app_runrequest SET result = %s WHERE id = %s;", (result_url, id,))
                        cur.execute("UPDATE app_runrequest SET state = 3 WHERE id = %s;", (id,))
                    elif run.state == "FAILED":
                        cur.execute("UPDATE app_runrequest SET state = 4 WHERE id = %s;", (id,))
                except Exception as e:
                    print(f"Error fetching run {run_id}:", e)
            conn.commit()
            cur.close()
        except Exception as e:
            print("Query error:", e)
        finally:
            conn.close()

    print("Job done.")