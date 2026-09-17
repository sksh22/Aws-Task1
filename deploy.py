import boto3
import zipfile  

REGION = "eu-north-1"
s3 = boto3.client("s3", region_name=REGION)                   #resource & session
cloudformation = boto3.client("cloudformation", region_name=REGION)

STACK_NAME = "s3-lambda-stack-03"
DEPLOY_BUCKET = "sksh-deploymentbucket-2026"
ZIP_FILE = "lambda_function.zip"

# 1. Create deployment bucket
try:
    s3.create_bucket(
        Bucket=DEPLOY_BUCKET,
        CreateBucketConfiguration={"LocationConstraint": REGION })
    print("Deployment bucket created.")
except s3.exceptions.BucketAlreadyOwnedByYou:
    print("Deployment bucket already exists.")

# 2. Create ZIP file
try:
    with zipfile.ZipFile(ZIP_FILE, "w") as zip_file:
        zip_file.write("lambda_function.py")
    print("Lambda ZIP created.")
except Exception as e:
    print(f"Error creating ZIP: {e}")
    raise

# 3. Upload ZIP to deployment bucket
try:
    s3.upload_file(ZIP_FILE, DEPLOY_BUCKET, ZIP_FILE)
    print("Lambda ZIP uploaded.")
except Exception as e:
    print(f"Error uploading ZIP: {e}")
    raise

# 4. Read CloudFormation template
with open("template.yaml", "r") as file:
    template = file.read()

# 5. Create CloudFormation stack
try:
    cloudformation.create_stack(
        StackName=STACK_NAME,
        TemplateBody=template,
        Parameters=[
            {
                "ParameterKey": "LambdaCodeBucket",
                "ParameterValue": DEPLOY_BUCKET
            },
            {
                "ParameterKey": "LambdaCodeKey",
                "ParameterValue": ZIP_FILE
            }], 
        Capabilities=["CAPABILITY_NAMED_IAM"])    
    print("CloudFormation stack creation started.")   
except Exception as e:
    print(f"Error creating CloudFormation stack: {e}")
    raise
