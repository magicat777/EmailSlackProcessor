#!/usr/bin/env python3
"""
Deploy ICAP Cloud Functions to Google Cloud Platform.
"""
import os
import sys
import yaml
import logging
import argparse
import subprocess
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("icap.deploy")

def load_config(config_file: str) -> Dict[str, Any]:
    """
    Load deployment configuration from YAML file.
    
    Args:
        config_file: Path to the configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded configuration from {config_file}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

def create_cloud_scheduler_job(project_id: str, 
                              region: str, 
                              function_name: str, 
                              function_url: str,
                              schedule: str,
                              service_account: Optional[str] = None) -> None:
    """
    Create or update a Cloud Scheduler job for the function.
    
    Args:
        project_id: Google Cloud project ID
        region: Region where the function is deployed
        function_name: Name of the Cloud Function
        function_url: URL to trigger the function
        schedule: Cron schedule expression
        service_account: Service account for the scheduler job
    """
    job_name = f"{function_name}-scheduler"
    
    # Check if job already exists
    check_cmd = [
        "gcloud", "scheduler", "jobs", "describe",
        job_name,
        f"--project={project_id}",
        f"--location={region}"
    ]
    
    job_exists = False
    try:
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        job_exists = result.returncode == 0
    except Exception:
        job_exists = False
    
    if job_exists:
        # Update existing job
        logger.info(f"Updating scheduler job: {job_name}")
        cmd = [
            "gcloud", "scheduler", "jobs", "update", "http",
            job_name,
            f"--project={project_id}",
            f"--location={region}",
            f"--schedule={schedule}",
            f"--uri={function_url}",
            "--http-method=POST",
            "--attempt-deadline=60s"
        ]
    else:
        # Create new job
        logger.info(f"Creating scheduler job: {job_name}")
        cmd = [
            "gcloud", "scheduler", "jobs", "create", "http",
            job_name,
            f"--project={project_id}",
            f"--location={region}",
            f"--schedule={schedule}",
            f"--uri={function_url}",
            "--http-method=POST",
            "--attempt-deadline=60s"
        ]
    
    # Add service account if provided
    if service_account:
        cmd.append(f"--oidc-service-account-email={service_account}")
        cmd.append("--oidc-token-audience=https://cloud.google.com/functions")
    
    # Run the command
    try:
        subprocess.run(cmd, check=True)
        logger.info(f"Successfully configured scheduler job: {job_name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error creating scheduler job: {e}")
        logger.error(f"Command output: {e.stdout}")
        logger.error(f"Command error: {e.stderr}")

def deploy_function(function_name: str, config: Dict[str, Any], 
                   base_path: str, dry_run: bool = False) -> str:
    """
    Deploy a Cloud Function.
    
    Args:
        function_name: Name of the function to deploy
        config: Configuration dictionary
        base_path: Base path for Cloud Functions
        dry_run: Whether to perform a dry run
        
    Returns:
        The URL of the deployed function
    """
    # Get global settings
    project_id = config.get('project_id', 'icap')
    region = config.get('region', 'us-central1')
    runtime = config.get('runtime', 'nodejs16')
    memory = config.get('memory', '256MB')
    timeout = config.get('timeout', '60s')
    service_account = config.get('service_account')
    
    # Get function-specific settings
    function_config = config.get('functions', {}).get(function_name, {})
    function_memory = function_config.get('memory', memory)
    function_timeout = function_config.get('timeout', timeout)
    
    # Merge environment variables
    env_vars = config.get('env_vars', {}).copy()
    function_env_vars = function_config.get('env_vars', {})
    env_vars.update(function_env_vars)
    
    # Convert env_vars to string
    env_vars_str = ",".join([f"{k}={v}" for k, v in env_vars.items()])
    
    # Build the deployment command
    function_path = os.path.join(base_path, function_name)
    
    if not os.path.exists(function_path):
        logger.error(f"Function directory not found: {function_path}")
        return ""
    
    # Determine entry points from package.json
    try:
        with open(os.path.join(function_path, "package.json"), 'r') as f:
            package_json = f.read()
        
        # Get the main file
        main_file = None
        if '"main":' in package_json:
            main_part = package_json.split('"main":', 1)[1].strip()
            main_file = main_part.split('"', 2)[1].replace('.js', '')
        
        if not main_file:
            main_file = "index"
        
        # Get exported functions from the main file
        main_file_path = os.path.join(function_path, f"{main_file}.js")
        with open(main_file_path, 'r') as f:
            js_content = f.read()
        
        # Find exports.functionName
        entry_points = []
        for line in js_content.split('\n'):
            if 'exports.' in line and '=' in line:
                parts = line.split('exports.', 1)[1].split('=', 1)[0].strip()
                if parts:
                    entry_points.append(parts)
        
        if not entry_points:
            logger.error(f"No entry points found in {main_file_path}")
            return ""
            
    except Exception as e:
        logger.error(f"Error analyzing function: {e}")
        return ""
    
    # Deploy each entry point
    function_urls = []
    
    for entry_point in entry_points:
        # Create full function name with entry point
        full_function_name = f"{function_name}-{entry_point}"
        
        logger.info(f"Deploying function: {full_function_name}")
        
        cmd = [
            "gcloud", "functions", "deploy", full_function_name,
            f"--project={project_id}",
            f"--region={region}",
            f"--runtime={runtime}",
            f"--memory={function_memory}",
            f"--timeout={function_timeout}",
            f"--entry-point={entry_point}",
            f"--source={function_path}",
            "--trigger-http",
            "--allow-unauthenticated"
        ]
        
        # Add service account if specified
        if service_account:
            cmd.append(f"--service-account={service_account}")
        
        # Add environment variables if specified
        if env_vars_str:
            cmd.append(f"--set-env-vars={env_vars_str}")
        
        # Run or print the command
        if dry_run:
            logger.info(f"Would run: {' '.join(cmd)}")
            function_url = f"https://{region}-{project_id}.cloudfunctions.net/{full_function_name}"
        else:
            try:
                logger.info(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Extract URL from output
                function_url = None
                for line in result.stdout.split('\n'):
                    if "httpsTrigger:" in line and "url:" in line:
                        function_url = line.split("url:", 1)[1].strip()
                        break
                
                if not function_url:
                    function_url = f"https://{region}-{project_id}.cloudfunctions.net/{full_function_name}"
                    
                logger.info(f"Function deployed successfully: {function_url}")
                
            except subprocess.CalledProcessError as e:
                logger.error(f"Error deploying function: {e}")
                logger.error(f"Command output: {e.stdout}")
                logger.error(f"Command error: {e.stderr}")
                continue
        
        function_urls.append(function_url)
        
        # Set up scheduler if configured
        schedule = function_config.get('schedule')
        if schedule and function_url:
            logger.info(f"Setting up scheduler for {full_function_name}: {schedule}")
            create_cloud_scheduler_job(
                project_id=project_id,
                region=region,
                function_name=full_function_name,
                function_url=function_url,
                schedule=schedule,
                service_account=service_account
            )
    
    # Return the first URL (or empty string if none)
    return function_urls[0] if function_urls else ""

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Deploy ICAP Cloud Functions")
    parser.add_argument("--config", default="cloud-functions/deployment.yaml",
                       help="Path to deployment configuration file")
    parser.add_argument("--project-id", help="Override Google Cloud project ID")
    parser.add_argument("--region", help="Override deployment region")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show deployment commands without executing")
    parser.add_argument("--all", action="store_true", 
                       help="Deploy all functions")
    parser.add_argument("functions", nargs="*", 
                       help="Names of functions to deploy")
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = os.path.abspath(args.config)
    config = load_config(config_path)
    
    # Override settings if provided
    if args.project_id:
        config['project_id'] = args.project_id
    if args.region:
        config['region'] = args.region
    
    # Determine which functions to deploy
    functions_to_deploy = args.functions
    if args.all or not functions_to_deploy:
        functions_to_deploy = list(config.get('functions', {}).keys())
    
    if not functions_to_deploy:
        logger.error("No functions specified and no functions found in configuration")
        sys.exit(1)
    
    # Calculate base path for cloud functions
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(os.path.dirname(script_dir), "cloud-functions")
    
    # Deploy each function
    for function_name in functions_to_deploy:
        deploy_function(function_name, config, base_path, args.dry_run)
    
    logger.info("Deployment completed")

if __name__ == "__main__":
    main()