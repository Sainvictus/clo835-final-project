from flask import Flask, render_template, request, send_from_directory
from pymysql import connections
import os
import random
import argparse
import boto3
import logging
import urllib.request
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Get environment variables with defaults for local development
DBHOST = os.environ.get("DBHOST") or "localhost"
DBUSER = os.environ.get("DBUSER") or "root"
DBPWD = os.environ.get("DBPWD") or "password"
DATABASE = os.environ.get("DATABASE") or "employees"
GROUP_NAME = os.environ.get("GROUP_NAME") or "CloudNative Warriors"
GROUP_SLOGAN = os.environ.get("GROUP_SLOGAN") or "Containerize, Orchestrate, Dominate!"
DBPORT = int(os.environ.get("DBPORT", "3306"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# S3 configuration from ConfigMap
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_KEY = os.environ.get("S3_KEY", "background1.jpg")
LOCAL_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# Ensure static directory exists
if not os.path.exists(LOCAL_IMAGE_PATH):
    os.makedirs(LOCAL_IMAGE_PATH)

background_image = None

def download_image_from_s3():
    """Download the background image from S3 to local storage"""
    if not S3_BUCKET:
        logger.warning("S3 bucket name not provided, skipping S3 download")
        return None
        
    try:
        s3_client = boto3.client('s3', region_name=AWS_REGION)
        local_file_path = os.path.join(LOCAL_IMAGE_PATH, os.path.basename(S3_KEY))
        
        logger.info(f"Downloading image from s3://{S3_BUCKET}/{S3_KEY} to {local_file_path}")
        s3_client.download_file(S3_BUCKET, S3_KEY, local_file_path)
        logger.info(f"Successfully downloaded the background image from S3")
        return os.path.basename(S3_KEY)
    except Exception as e:
        logger.error(f"Error downloading image from S3: {e}")
        # Create a fallback image
        create_fallback_image()
        return "fallback.jpg"

def create_fallback_image():
    """Create a simple fallback image when S3 access fails"""
    try:
        # Create a simple HTML file that will serve as our background
        fallback_path = os.path.join(LOCAL_IMAGE_PATH, "fallback.jpg")
        
        # Download a fallback image from a public URL
        fallback_url = "https://via.placeholder.com/1920x1080/0066cc/ffffff?text=CLO835+Final+Project"
        try:
            urllib.request.urlretrieve(fallback_url, fallback_path)
            logger.info("Created fallback image from placeholder service")
        except Exception as e:
            logger.error(f"Could not create fallback image from URL: {e}")
            # If download fails, create an empty file
            with open(fallback_path, 'wb') as f:
                f.write(b'')
            logger.info("Created empty fallback image")
    except Exception as e:
        logger.error(f"Error creating fallback image: {e}")

# Try to connect to the database
try:
    db_conn = connections.Connection(
        host=DBHOST,
        port=DBPORT,
        user=DBUSER,
        password=DBPWD,
        db=DATABASE
    )
    logger.info(f"Connected to MySQL database: {DATABASE} at {DBHOST}")
except Exception as e:
    logger.error(f"Database connection failed: {e}")
    db_conn = None

# Try to download the image at startup, use fallback if it fails
try:
    background_image = download_image_from_s3()
    if background_image:
        logger.info(f"Using background image: {background_image}")
    else:
        logger.warning("Could not download background image, will use fallback")
        create_fallback_image()
        background_image = "fallback.jpg"
except Exception as e:
    logger.error(f"Error setting up background image: {e}")
    create_fallback_image()
    background_image = "fallback.jpg"

@app.route("/", methods=['GET', 'POST'])
def home():
    return render_template('addemp.html', 
                          background_image=background_image,
                          group_name=GROUP_NAME,
                          group_slogan=GROUP_SLOGAN)

@app.route("/about", methods=['GET', 'POST'])
def about():
    return render_template('about.html', 
                           background_image=background_image,
                           group_name=GROUP_NAME,
                           group_slogan=GROUP_SLOGAN)

@app.route("/addemp", methods=['POST'])
def AddEmp():
    emp_id = request.form['emp_id']
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    primary_skill = request.form['primary_skill']
    location = request.form['location']

    if db_conn:
        insert_sql = "INSERT INTO employee VALUES (%s, %s, %s, %s, %s)"
        cursor = db_conn.cursor()

        try:
            cursor.execute(insert_sql, (emp_id, first_name, last_name, primary_skill, location))
            db_conn.commit()
            emp_name = f"{first_name} {last_name}"
            logger.info(f"Added employee: {emp_name}")
        except Exception as e:
            logger.error(f"Error adding employee: {e}")
            emp_name = "Error"
        finally:
            cursor.close()
    else:
        emp_name = "Database connection not available"
        logger.warning("Attempted to add employee but database connection not available")

    return render_template('addempoutput.html', 
                           name=emp_name, 
                           background_image=background_image,
                           group_name=GROUP_NAME,
                           group_slogan=GROUP_SLOGAN)

@app.route("/getemp", methods=['GET', 'POST'])
def GetEmp():
    return render_template("getemp.html", 
                           background_image=background_image,
                           group_name=GROUP_NAME,
                           group_slogan=GROUP_SLOGAN)

@app.route("/fetchdata", methods=['GET', 'POST'])
def FetchData():
    emp_id = request.form['emp_id']
    output = {"emp_id": "", "first_name": "", "last_name": "", "primary_skills": "", "location": ""}
    
    if db_conn:
        select_sql = "SELECT emp_id, first_name, last_name, primary_skill, location from employee where emp_id=%s"
        cursor = db_conn.cursor()

        try:
            cursor.execute(select_sql, (emp_id,))
            result = cursor.fetchone()
            
            if result:
                output["emp_id"] = result[0]
                output["first_name"] = result[1]
                output["last_name"] = result[2]
                output["primary_skills"] = result[3]
                output["location"] = result[4]
                logger.info(f"Retrieved employee data for ID: {emp_id}")
            else:
                logger.warning(f"No employee found with ID: {emp_id}")
                
        except Exception as e:
            logger.error(f"Error fetching employee data: {e}")
        finally:
            cursor.close()
    else:
        logger.warning("Attempted to fetch employee but database connection not available")

    return render_template("getempoutput.html", 
                           id=output["emp_id"], 
                           fname=output["first_name"],
                           lname=output["last_name"], 
                           interest=output["primary_skills"], 
                           location=output["location"],
                           background_image=background_image,
                           group_name=GROUP_NAME,
                           group_slogan=GROUP_SLOGAN)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/health')
def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--s3bucket', required=False)
    parser.add_argument('--s3key', required=False)
    args = parser.parse_args()

    if args.s3bucket:
        S3_BUCKET = args.s3bucket
    if args.s3key:
        S3_KEY = args.s3key
        try:
            background_image = download_image_from_s3()
            if not background_image:
                create_fallback_image()
                background_image = "fallback.jpg"
        except:
            create_fallback_image()
            background_image = "fallback.jpg"
        
    logger.info(f"S3 Bucket: {S3_BUCKET}, S3 Key: {S3_KEY}")
    logger.info(f"Background Image: {background_image}")
    logger.info(f"Group Name: {GROUP_NAME}, Group Slogan: {GROUP_SLOGAN}")
    
    app.run(host='0.0.0.0', port=81, debug=True)
