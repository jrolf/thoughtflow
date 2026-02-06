"""
RUN action - execute shell commands.

Uses only Python standard library (subprocess).
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time as time_module

from thoughtflow.action import ACTION
from thoughtflow.actions._substitution import substitute


class RUN(ACTION):
    """
    An action that executes shell commands.
    
    RUN provides a safe interface for executing shell commands with
    configurable timeout, output capture, and error handling.
    
    SECURITY NOTE: RUN executes arbitrary commands. Always validate
    and sanitize any user-provided input before including in commands.
    
    Args:
        name (str): Unique identifier for this action.
        command (str|list|callable): Command to execute. Can be:
            - str: Shell command with {variable} placeholders
            - list: Command and arguments as list
            - callable: Function (memory) -> str|list
        cwd (str): Working directory for command.
        env (dict): Environment variables (merged with current env).
        timeout (float): Command timeout in seconds (None = no timeout).
        capture (bool): Capture stdout/stderr (default: True).
        shell (bool): Run command in shell (default: True for str, False for list).
        on_error (str): Error handling:
            - "log": Log error and continue (default)
            - "raise": Raise exception on non-zero exit
            - "ignore": Silently continue
        store_as (str): Memory variable for result (default: "{name}_result").
    
    Example:
        >>> from thoughtflow.actions import RUN
        >>> from thoughtflow import MEMORY
        
        # Simple command
        >>> run = RUN(command="echo 'Hello, World!'")
        >>> memory = run(MEMORY())
        >>> result = memory.get_var("run_result")
        >>> print(result["stdout"])
        Hello, World!
        
        # Command with variables
        >>> run = RUN(
        ...     command="grep '{pattern}' {file}",
        ...     timeout=30
        ... )
        
        # Command as list (safer, no shell)
        >>> run = RUN(
        ...     command=["python", "-c", "print('Hello')"],
        ...     shell=False
        ... )
        
        # With working directory and environment
        >>> run = RUN(
        ...     command="make build",
        ...     cwd="/path/to/project",
        ...     env={"DEBUG": "1"}
        ... )
        
        # Dynamic command
        >>> run = RUN(
        ...     command=lambda m: "process {}".format(m.get_var("input_file"))
        ... )
    
    Returns:
        dict: {
            "command": str,
            "return_code": int,
            "stdout": str,
            "stderr": str,
            "elapsed_ms": float,
            "success": bool
        }
    """
    
    def __init__(
        self,
        name=None,
        command=None,
        cwd=None,
        env=None,
        timeout=None,
        capture=True,
        shell=None,
        on_error="log",
        store_as=None,
    ):
        """
        Initialize a RUN action.
        
        Args:
            name: Optional name (defaults to "run").
            command: Command to execute.
            cwd: Working directory.
            env: Environment variables.
            timeout: Command timeout.
            capture: Capture output.
            shell: Use shell execution.
            on_error: Error behavior.
            store_as: Memory variable name.
        """
        if command is None:
            raise ValueError("RUN requires 'command' parameter")
        
        self.command = command
        self.cwd = cwd
        self.env = env
        self.timeout = timeout
        self.capture = capture
        self.on_error = on_error
        
        # Default shell based on command type
        if shell is None:
            shell = isinstance(command, str)
        self.shell = shell
        
        name = name or "run"
        
        super().__init__(
            name=name,
            fn=self._execute,
            result_key=store_as or "{}_result".format(name),
            description="RUN: Execute shell command"
        )
    
    def _execute(self, memory, **kwargs):
        """
        Execute the RUN action.
        
        Args:
            memory: MEMORY instance.
            **kwargs: Can override parameters.
        
        Returns:
            dict: Command execution result.
        """
        # Get parameters
        command = kwargs.get('command', self.command)
        cwd = kwargs.get('cwd', self.cwd)
        env = kwargs.get('env', self.env)
        timeout = kwargs.get('timeout', self.timeout)
        capture = kwargs.get('capture', self.capture)
        shell = kwargs.get('shell', self.shell)
        on_error = kwargs.get('on_error', self.on_error)
        
        # Resolve command
        command = substitute(command, memory)
        if command is None:
            raise ValueError("RUN command cannot be None")
        
        # Resolve cwd
        cwd = substitute(cwd, memory)
        if cwd:
            cwd = os.path.expanduser(str(cwd))
        
        # Prepare environment
        run_env = os.environ.copy()
        if env:
            resolved_env = substitute(env, memory) or {}
            run_env.update({str(k): str(v) for k, v in resolved_env.items()})
        
        # Prepare command for subprocess
        if isinstance(command, str):
            cmd_for_log = command
            cmd = command if shell else shlex.split(command)
        else:
            cmd_for_log = ' '.join(str(c) for c in command)
            cmd = command
        
        # Prepare subprocess arguments
        proc_kwargs = {
            "cwd": cwd,
            "env": run_env,
            "shell": shell if isinstance(cmd, str) else False,
        }
        
        if capture:
            proc_kwargs["stdout"] = subprocess.PIPE
            proc_kwargs["stderr"] = subprocess.PIPE
        
        # Execute command
        start_time = time_module.time()
        
        try:
            result = subprocess.run(
                cmd,
                timeout=timeout,
                **proc_kwargs
            )
            
            elapsed_ms = (time_module.time() - start_time) * 1000
            
            # Build result
            output = {
                "command": cmd_for_log,
                "return_code": result.returncode,
                "stdout": result.stdout.decode('utf-8', errors='replace') if capture and result.stdout else "",
                "stderr": result.stderr.decode('utf-8', errors='replace') if capture and result.stderr else "",
                "elapsed_ms": round(elapsed_ms, 2),
                "success": result.returncode == 0
            }
            
            # Handle non-zero exit code
            if result.returncode != 0:
                return self._handle_error(
                    output, None, on_error, memory
                )
            
            return output
            
        except subprocess.TimeoutExpired as e:
            elapsed_ms = (time_module.time() - start_time) * 1000
            output = {
                "command": cmd_for_log,
                "return_code": -1,
                "stdout": e.stdout.decode('utf-8', errors='replace') if capture and e.stdout else "",
                "stderr": e.stderr.decode('utf-8', errors='replace') if capture and e.stderr else "",
                "elapsed_ms": round(elapsed_ms, 2),
                "success": False,
                "error": "Command timed out after {} seconds".format(timeout)
            }
            return self._handle_error(output, e, on_error, memory)
            
        except Exception as e:
            elapsed_ms = (time_module.time() - start_time) * 1000
            output = {
                "command": cmd_for_log,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "elapsed_ms": round(elapsed_ms, 2),
                "success": False,
                "error": str(e)
            }
            return self._handle_error(output, e, on_error, memory)
    
    def _handle_error(self, output, exception, on_error, memory):
        """
        Handle command execution error.
        
        Args:
            output: Execution result dict.
            exception: Exception if any.
            on_error: Error behavior.
            memory: MEMORY instance.
        
        Returns:
            dict: Output dict.
        
        Raises:
            Exception: If on_error="raise".
        """
        if on_error == "raise":
            if exception:
                raise exception
            raise subprocess.CalledProcessError(
                output["return_code"],
                output["command"],
                output.get("stdout", ""),
                output.get("stderr", "")
            )
        
        if on_error == "log":
            if hasattr(memory, 'add_log'):
                error_msg = output.get("error") or output.get("stderr", "Unknown error")
                memory.add_log("RUN failed (code {}): {}".format(
                    output["return_code"], error_msg[:200]
                ))
        
        # on_error == "ignore" - just return the output
        return output
    
    def to_dict(self):
        """
        Serialize RUN to dictionary.
        
        Returns:
            dict: Serializable representation.
        """
        base = super().to_dict()
        base["_class"] = "RUN"
        base["cwd"] = self.cwd
        base["timeout"] = self.timeout
        base["capture"] = self.capture
        base["shell"] = self.shell
        base["on_error"] = self.on_error
        if not callable(self.command):
            base["command"] = self.command
        if not callable(self.env):
            base["env"] = self.env
        return base
    
    @classmethod
    def from_dict(cls, data, **kwargs):
        """
        Reconstruct RUN from dictionary.
        
        Args:
            data: Dictionary representation.
            **kwargs: Ignored.
        
        Returns:
            RUN: Reconstructed instance.
        """
        run = cls(
            name=data.get("name"),
            command=data.get("command"),
            cwd=data.get("cwd"),
            env=data.get("env"),
            timeout=data.get("timeout"),
            capture=data.get("capture", True),
            shell=data.get("shell"),
            on_error=data.get("on_error", "log"),
            store_as=data.get("result_key")
        )
        if data.get("id"):
            run.id = data["id"]
        return run
    
    def __repr__(self):
        cmd = "<callable>" if callable(self.command) else repr(
            self.command[:50] + "..." if isinstance(self.command, str) and len(self.command) > 50 else self.command
        )
        return "RUN(name='{}', command={})".format(self.name, cmd)
    
    def __str__(self):
        if callable(self.command):
            return "RUN <dynamic command>"
        if isinstance(self.command, str):
            preview = self.command[:40]
            if len(self.command) > 40:
                preview += "..."
            return "RUN: {}".format(preview)
        return "RUN: {}".format(' '.join(str(c) for c in self.command[:3]))
