import logging # Import the logging module to log messages
import boto3  # Import the boto3 library to interact with AWS services
import zipfile  # Import the zipfile module to create ZIP files
from botocore.exceptions import ClientError # Import ClientError to handle exceptions from boto3
import uuid
import json
import time
import textwrap


import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO) # Set the logging level to INFO

# Setup variables
region = "us-east-1"  # Change to your desired region
lambdas_iam_role = "arn:aws:iam::<account-id>:role/service-role/<your-lambda-execution-role-name>"  # Replace with your IAM role ARN
myvar = "myvariable"  # You can replace with your variable
template_name = "dynamic-function-test"  # Default value for the target function name

# Setup boto3 clients
lambda_client = boto3.client('lambda', region_name=region)  # Create a Lambda client
s3_client = boto3.client('s3', region_name=region)  # Create an S3 client


def create_lambda_function(target_name):
    try:
        # Generate Lambda function code
        lambda_code = textwrap.dedent(f"""\
        import json
        import boto3

        region = '{region}'
        template_name = '{target_name}'

        lambda_client = boto3.client('lambda', region_name=region)

        def lambda_handler(event, context):
            print(json.dumps(event))
            parsed_event = json.loads(json.dumps(event))
            user_id = parsed_event.get('user_id', 'unknown')
            print(f"Processed user ID: {{user_id}}")
            return {{
                "status": "ok",
                "user_id": user_id
            }}
        """)

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

        # Wait for it to become Active
        if wait_for_function_active(target_name):
            # Add invoke permission
            lambda_client.add_permission(
                FunctionName=target_name,
                StatementId=f"AllowAllInvoke-{uuid.uuid4().hex[:8]}",
                Action="lambda:InvokeFunction",
                Principal="*"
            )

            # Invoke the function
            invoke_response = lambda_client.invoke(
                FunctionName=target_name,
                InvocationType='RequestResponse',
                Payload=json.dumps({"user_id": "abc123"})
            )
            logger.info(f"Invoked {target_name} - StatusCode: {invoke_response['StatusCode']}")
            response_payload = invoke_response['Payload'].read().decode('utf-8')
            logger.info(f"Invocation output: {response_payload}")
        else:
            logger.error(f"Failed to invoke {target_name}: function did not become Active")


        return response
    except ClientError as e:
        logger.error(f"Failed to create function {target_name}: {e}")
        return None

def wait_for_function_active(function_name, retries=5, delay=1):
    # Log the overall waiting 
    logger.info(f"Waiting for function '{function_name}' to reach Active state (max {retries} attempts, {delay}s delay)...")
    
    # Loop to retry the check up to `retries` times
    for attempt in range(1, retries + 1):
        try:
            # Call AWS Lambda API to get the function's current configuration and state
            response = lambda_client.get_function(FunctionName=function_name)
            status = response['Configuration']['State']

            # Check if the function is now active
            if status == 'Active':
                # Function is ready to be invoked
                logger.info(f"Function '{function_name}' is Active after {attempt} attempt(s).")
                return True
            else:
                # Function is still being initialized, retry after a delay
                logger.info(f"[Attempt {attempt}] Function '{function_name}' not active yet (state: {status}), retrying in {delay}s...")

        except ClientError as e:
            # If there's an API error (e.g., permission or network), log and continue retrying
            logger.warning(f"[Attempt {attempt}] Error checking function state for '{function_name}': {e}")

        # Wait before the next attempt
        time.sleep(delay)

    # If function never becomes active within the retry window, log failure
    logger.error(f"Function '{function_name}' did not become Active within {retries} attempts.")
    return False


def lambda_handler(event, context):
    target_function_name = event.get('name', f"{template_name}-{uuid.uuid4().hex[:6]}")
    logger.info(f"Received request to create function: {target_function_name}")
    response = create_lambda_function(target_function_name)
    if response:
        logger.info(f"Function {target_function_name} created successfully")
    else:
        logger.error(f"Failed to create function {target_function_name}")
