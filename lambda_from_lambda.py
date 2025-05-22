import logging # Import the logging module to log messages
import boto3  # Import the boto3 library to interact with AWS services
import zipfile  # Import the zipfile module to create ZIP files
from botocore.exceptions import ClientError # Import ClientError to handle exceptions from boto3

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO) # Set the logging level to INFO

# Setup variables
region = "us-east-1"  # Change to your desired region
lambdas_iam_role = "arn:aws:iam::<account-id>:role/service-role/<your-lambda-execution-role-name>"  # Replace with your IAM role ARN
myvar = "myvariable"  # You can replace with your variable
template_name = "mytemplate"  # Default value for the target function name

# Setup boto3 clients
lambda_client = boto3.client('lambda', region_name=region)  # Create a Lambda client
s3_client = boto3.client('s3', region_name=region)  # Create an S3 client


def create_lambda_function(target_name):
    try:
        # Generate Lambda function code
        lambda_code = f"""
        import json
        import boto3

        # Setup variables
        region = '{region}'
        template_name = '{target_name}'

        # Setup clients
        lambda_client = boto3.client('lambda', region_name=region)

        def lambda_handler(event, context):
            print(json.dumps(event))
            parsed_event = json.loads(json.dumps(event))
            user_id = parsed_event.get('user_id', 'unknown')
            print(f"Processed user ID: {user_id}")
        """

        # Create a ZIP file with the Lambda code
        zip_path = '/tmp/lambda_code.zip'
        with zipfile.ZipFile(zip_path, 'w') as zfs:
            zip_info = zipfile.ZipInfo('lambda_function.py')
            zfs.writestr(zip_info, lambda_code)

        # Create the Lambda function
        response = lambda_client.create_function(
            FunctionName=target_name,
            Runtime='python3.11',
            Role=lambdas_iam_role,
            Handler='lambda_function.lambda_handler',
            Code={'ZipFile': open(zip_path, 'rb').read()},
            Environment={'Variables': {'mylambdavariable': myvar}},
            Architectures=['arm64'],
            Description=f'Lambda function for {target_name}',
            Timeout=30,
            MemorySize=256
        )
        logger.info(f"Created function: {target_name}")
        return response
    except ClientError as e:
        logger.error(f"Failed to create function {target_name}: {e}")
        return None

def lambda_handler(event, context):
    target_function_name = event.get('name', template_name)
    logger.info(f"Received request to create function: {target_function_name}")
    response = create_lambda_function(target_function_name)
    if response:
        logger.info(f"Function {target_function_name} created successfully")
    else:
        logger.error(f"Failed to create function {target_function_name}")
