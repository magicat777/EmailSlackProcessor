"""
Webhook endpoints for ICAP pipeline triggers.
"""
import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from aiohttp import web
from python_components.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger("icap.webhook")

class WebhookHandler:
    """Handler for webhook requests that trigger pipeline processing."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """
        Initialize the webhook handler.
        
        Args:
            host: Host to bind the server
            port: Port to bind the server
        """
        self.host = host
        self.port = port
        self.app = web.Application()
        self.orchestrator = PipelineOrchestrator()
        self._setup_routes()
        logger.info(f"Webhook handler initialized on {host}:{port}")
    
    def _setup_routes(self) -> None:
        """Set up the webhook routes."""
        self.app.add_routes([
            web.post('/webhook/email', self.handle_email_webhook),
            web.post('/webhook/slack', self.handle_slack_webhook),
            web.post('/webhook/summary', self.handle_summary_webhook),
            web.get('/health', self.health_check)
        ])
    
    async def start(self) -> None:
        """Start the webhook server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"Webhook server started on http://{self.host}:{self.port}")
    
    async def handle_email_webhook(self, request: web.Request) -> web.Response:
        """
        Handle webhook requests for email processing.
        
        Args:
            request: The HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Validate the webhook token for security
            if not self._validate_webhook_token(request):
                return web.json_response(
                    {"error": "Invalid webhook token"}, 
                    status=401
                )
            
            # Parse the request body
            body = await request.json()
            logger.info(f"Received email webhook: {body}")
            
            # Start the email processing pipeline
            asyncio.create_task(self._process_email_webhook(body))
            
            return web.json_response({
                "status": "processing",
                "message": "Email processing started",
                "timestamp": datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook request")
            return web.json_response(
                {"error": "Invalid JSON"}, 
                status=400
            )
            
        except Exception as e:
            logger.error(f"Error handling email webhook: {str(e)}")
            return web.json_response(
                {"error": str(e)}, 
                status=500
            )
    
    async def handle_slack_webhook(self, request: web.Request) -> web.Response:
        """
        Handle webhook requests for Slack processing.
        
        Args:
            request: The HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Validate the webhook token for security
            if not self._validate_webhook_token(request):
                return web.json_response(
                    {"error": "Invalid webhook token"}, 
                    status=401
                )
            
            # Parse the request body
            body = await request.json()
            logger.info(f"Received Slack webhook: {body}")
            
            # Start the Slack processing pipeline
            asyncio.create_task(self._process_slack_webhook(body))
            
            return web.json_response({
                "status": "processing",
                "message": "Slack processing started",
                "timestamp": datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook request")
            return web.json_response(
                {"error": "Invalid JSON"}, 
                status=400
            )
            
        except Exception as e:
            logger.error(f"Error handling Slack webhook: {str(e)}")
            return web.json_response(
                {"error": str(e)}, 
                status=500
            )
    
    async def handle_summary_webhook(self, request: web.Request) -> web.Response:
        """
        Handle webhook requests for summary generation.
        
        Args:
            request: The HTTP request
            
        Returns:
            HTTP response
        """
        try:
            # Validate the webhook token for security
            if not self._validate_webhook_token(request):
                return web.json_response(
                    {"error": "Invalid webhook token"}, 
                    status=401
                )
            
            # Parse the request body (may be empty)
            try:
                body = await request.json()
            except:
                body = {}
                
            logger.info(f"Received summary webhook: {body}")
            
            # Start the summary generation pipeline
            asyncio.create_task(self._process_summary_webhook(body))
            
            return web.json_response({
                "status": "processing",
                "message": "Summary generation started",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error handling summary webhook: {str(e)}")
            return web.json_response(
                {"error": str(e)}, 
                status=500
            )
    
    async def health_check(self, request: web.Request) -> web.Response:
        """
        Health check endpoint.
        
        Args:
            request: The HTTP request
            
        Returns:
            HTTP response
        """
        return web.json_response({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "pipeline_history_count": len(self.orchestrator.pipeline_history)
        })
    
    async def _process_email_webhook(self, body: Dict[str, Any]) -> None:
        """
        Process an email webhook in the background.
        
        Args:
            body: The webhook request body
        """
        try:
            # Extract the query parameters
            query = {
                "maxResults": body.get("maxResults", 10),
                "filter": body.get("filter", "isRead eq false")
            }
            
            # Run the pipeline
            context = await self.orchestrator.process_email(query)
            
            logger.info(f"Email pipeline completed with status: {context.status}")
            if context.status == "failed":
                logger.error(f"Email pipeline error: {context.error}")
                
        except Exception as e:
            logger.error(f"Error in _process_email_webhook: {str(e)}")
    
    async def _process_slack_webhook(self, body: Dict[str, Any]) -> None:
        """
        Process a Slack webhook in the background.
        
        Args:
            body: The webhook request body
        """
        try:
            # Extract the query parameters
            query = {
                "maxResults": body.get("maxResults", 50),
                "channels": body.get("channels", []),
                "olderThan": body.get("olderThan")
            }
            
            # Run the pipeline
            context = await self.orchestrator.process_slack(query)
            
            logger.info(f"Slack pipeline completed with status: {context.status}")
            if context.status == "failed":
                logger.error(f"Slack pipeline error: {context.error}")
                
        except Exception as e:
            logger.error(f"Error in _process_slack_webhook: {str(e)}")
    
    async def _process_summary_webhook(self, body: Dict[str, Any]) -> None:
        """
        Process a summary webhook in the background.
        
        Args:
            body: The webhook request body
        """
        try:
            # Run the pipeline
            context = await self.orchestrator.generate_daily_summary()
            
            logger.info(f"Summary pipeline completed with status: {context.status}")
            if context.status == "failed":
                logger.error(f"Summary pipeline error: {context.error}")
                
        except Exception as e:
            logger.error(f"Error in _process_summary_webhook: {str(e)}")
    
    def _validate_webhook_token(self, request: web.Request) -> bool:
        """
        Validate the webhook token in the request.
        
        Args:
            request: The HTTP request
            
        Returns:
            True if the token is valid, False otherwise
        """
        # Get the expected token from environment
        expected_token = os.getenv("WEBHOOK_TOKEN")
        if not expected_token:
            logger.warning("WEBHOOK_TOKEN not set in environment")
            return False
        
        # Get the token from the request
        token = None
        
        # Check the Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        # If no token in header, check the query string
        if not token:
            token = request.query.get("token")
        
        # If still no token, check the body
        if not token and request.body_exists:
            try:
                body = request.json()
                token = body.get("token")
            except:
                pass
        
        # Validate the token
        if not token:
            logger.warning("No token found in request")
            return False
        
        return token == expected_token