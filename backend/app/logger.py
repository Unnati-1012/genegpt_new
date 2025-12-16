# backend/app/logger.py
"""
Centralized logging configuration for GeneGPT.
Provides colored, structured console logging for all operations.
"""

import logging
import sys
from datetime import datetime
from typing import Optional


# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    
    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


class NoviqFormatter(logging.Formatter):
    """Custom formatter with colors and emojis for different log levels and categories."""
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BRIGHT_RED + Colors.BOLD,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Get color for log level
        color = self.LEVEL_COLORS.get(record.levelno, Colors.WHITE)
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Build the log message
        level_name = record.levelname.ljust(8)
        
        formatted = (
            f"{Colors.BRIGHT_BLUE}[{timestamp}]{Colors.RESET} "
            f"{color}{level_name}{Colors.RESET} "
            f"{record.getMessage()}"
        )
        
        return formatted


class NoviqLogger:
    """
    Centralized logger for Noviq.AI with specialized logging methods.
    """
    
    def __init__(self, name: str = "Noviq.AI"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Console handler with custom formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(NoviqFormatter())
        
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    # ===========================================
    # GENERAL LOGGING
    # ===========================================
    
    def debug(self, message: str) -> None:
        """Log a debug message."""
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log an informational message."""
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log an error message."""
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        """Log a critical error message."""
        self.logger.critical(message)
    
    # ===========================================
    # SPECIALIZED LOGGING METHODS
    # ===========================================
    
    def incoming_request(self, endpoint: str, message: str) -> None:
        """
        Log an incoming API request.
        
        Args:
            endpoint: API endpoint path (e.g., "/chat")
            message: The request message/query (truncated to 100 chars)
        """
        self.logger.info(
            f"{Colors.BRIGHT_MAGENTA}📩 INCOMING{Colors.RESET} "
            f"[{Colors.CYAN}{endpoint}{Colors.RESET}] "
            f"{Colors.WHITE}{message[:100]}{'...' if len(message) > 100 else ''}{Colors.RESET}"
        )
    
    def query_classification(self, query_type: str, db_type: Optional[str], search_term: Optional[str], needs_clarification: bool = False) -> None:
        """
        Log query classification results from the LLM.
        
        Args:
            query_type: "general" or "medical"
            db_type: Target database (e.g., "uniprot", "pdb") or None
            search_term: Extracted search term or None
            needs_clarification: Whether the query needs user clarification
        """
        if query_type == "general":
            self.logger.info(
                f"{Colors.BRIGHT_YELLOW}🏷️  CLASSIFIED{Colors.RESET} "
                f"type={Colors.YELLOW}general{Colors.RESET}"
            )
        elif needs_clarification:
            self.logger.info(
                f"{Colors.BRIGHT_YELLOW}🏷️  CLASSIFIED{Colors.RESET} "
                f"type={Colors.MAGENTA}medical{Colors.RESET} "
                f"| {Colors.YELLOW}needs_clarification=True{Colors.RESET}"
            )
        else:
            self.logger.info(
                f"{Colors.BRIGHT_YELLOW}🏷️  CLASSIFIED{Colors.RESET} "
                f"type={Colors.MAGENTA}medical{Colors.RESET} "
                f"| db={Colors.CYAN}{db_type}{Colors.RESET} "
                f"| term={Colors.GREEN}{search_term}{Colors.RESET}"
            )
    
    def database_hit(self, db_name: str, search_term: str, sub_command: Optional[str] = None) -> None:
        """
        Log when a database is being queried.
        
        Args:
            db_name: Database identifier (e.g., "uniprot", "pdb")
            search_term: The search query being sent
            sub_command: Optional sub-command (e.g., "mmcif", "pubmed")
        """
        db_colors = {
            "uniprot": Colors.BRIGHT_BLUE,
            "string": Colors.BRIGHT_GREEN,
            "pubchem": Colors.BRIGHT_MAGENTA,
            "pdb": Colors.BRIGHT_CYAN,
            "ncbi": Colors.BRIGHT_YELLOW,
            "kegg": Colors.GREEN,
            "ensembl": Colors.MAGENTA,
            "clinvar": Colors.RED,
            "image_search": Colors.CYAN,
        }
        
        color = db_colors.get(db_name.lower(), Colors.WHITE)
        
        sub_cmd_str = f" ({sub_command})" if sub_command else ""
        
        self.logger.info(
            f"{Colors.BRIGHT_CYAN}🔀 DATABASE HIT{Colors.RESET} "
            f"→ {color}{Colors.BOLD}{db_name.upper()}{Colors.RESET}{sub_cmd_str} "
            f"| query={Colors.WHITE}'{search_term}'{Colors.RESET}"
        )
    
    def database_result(self, db_name: str, success: bool, record_count: Optional[int] = None, error: Optional[str] = None) -> None:
        """
        Log database query result.
        
        Args:
            db_name: Database identifier
            success: Whether the query succeeded
            record_count: Number of records returned (if successful)
            error: Error message (if failed)
        """
        if success:
            count_str = f" | records={record_count}" if record_count is not None else ""
            self.logger.info(
                f"{Colors.BRIGHT_GREEN}✅ DB SUCCESS{Colors.RESET} "
                f"[{db_name.upper()}]{count_str}"
            )
        else:
            self.logger.warning(
                f"{Colors.BRIGHT_RED}❌ DB FAILED{Colors.RESET} "
                f"[{db_name.upper()}] error={error}"
            )
    
    def llm_call(self, purpose: str, model: str) -> None:
        """
        Log LLM API call initiation.
        
        Args:
            purpose: Purpose of the call (e.g., "query_classification", "answer_generation")
            model: Model name being used
        """
        self.logger.info(
            f"{Colors.BRIGHT_MAGENTA}🤖 LLM CALL{Colors.RESET} "
            f"purpose={Colors.YELLOW}{purpose}{Colors.RESET} "
            f"| model={Colors.CYAN}{model}{Colors.RESET}"
        )
    
    def llm_response(self, purpose: str, tokens_hint: Optional[int] = None) -> None:
        """
        Log LLM response received.
        
        Args:
            purpose: Purpose of the call
            tokens_hint: Approximate character count of response
        """
        tokens_str = f" | ~{tokens_hint} chars" if tokens_hint else ""
        self.logger.info(
            f"{Colors.BRIGHT_GREEN}✨ LLM RESPONSE{Colors.RESET} "
            f"purpose={Colors.YELLOW}{purpose}{Colors.RESET}{tokens_str}"
        )
    
    def router_decision(self, from_source: str, to_target: str, reason: str = "") -> None:
        """
        Log routing decisions.
        
        Args:
            from_source: Source of the routing decision
            to_target: Target destination
            reason: Optional reason for the routing
        """
        reason_str = f" ({reason})" if reason else ""
        self.logger.debug(
            f"{Colors.CYAN}🔄 ROUTE{Colors.RESET} "
            f"{from_source} → {Colors.GREEN}{to_target}{Colors.RESET}{reason_str}"
        )
    
    def response_sent(self, has_html: bool = False, reply_length: int = 0) -> None:
        """
        Log when response is sent back to client.
        
        Args:
            has_html: Whether the response contains HTML content
            reply_length: Length of the text reply
        """
        html_str = f" | {Colors.CYAN}+HTML{Colors.RESET}" if has_html else ""
        self.logger.info(
            f"{Colors.BRIGHT_GREEN}📤 RESPONSE SENT{Colors.RESET} "
            f"reply_length={reply_length}{html_str}"
        )
    
    def separator(self, title: str = "") -> None:
        """
        Print a visual separator for readability in logs.
        
        Args:
            title: Optional title to display in the separator
        """
        if title:
            self.logger.info(
                f"{Colors.BRIGHT_BLUE}{'─' * 20} {title} {'─' * 20}{Colors.RESET}"
            )
        else:
            self.logger.info(f"{Colors.BRIGHT_BLUE}{'─' * 50}{Colors.RESET}")


# Global logger instance
logger = NoviqLogger()


# Convenience function to get the logger
def get_logger() -> NoviqLogger:
    return logger
