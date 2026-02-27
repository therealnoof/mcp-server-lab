"""
=============================================================
 PHASE 1 - THE AGENT: SOC Analyst AI
=============================================================
 What this file does:
   This is the "brain" of our Phase 1 lab. It's an AI agent
   that acts like a junior SOC analyst.
   
   Here's the flow:
   
   1. Agent connects to the MCP Server and DISCOVERS what
      tools are available (it doesn't know ahead of time!)
   
   2. Agent converts those MCP tools into a format Ollama
      understands (OpenAI-compatible tool/function format)
   
   3. Agent sends the user's query to the local LLM (Ollama)
      along with the list of available tools
   
   4. The LLM decides WHICH tools to call and with WHAT arguments
      (this is the "reasoning" part - the LLM figures this out)
   
   5. We execute those tool calls through MCP and send the
      results BACK to the LLM
   
   6. The LLM uses the tool results to write a final analysis
   
   This loop (steps 4-6) repeats until the LLM has enough
   information and stops calling tools. That's the "agent loop."
=============================================================
"""

import asyncio
import json
import os
import sys
import time
import ollama
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

# -------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------
# These can be overridden with environment variables,
# which makes Docker configuration easier.
# -------------------------------------------------------

# URL of the MCP server - in Docker this uses the service name
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8000/sse")

# URL of the Ollama server - in Docker this uses the service name
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

# Which LLM model to use. llama3.1:8b is good for function calling
# and fits comfortably in a T4's 16GB VRAM
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

# How many times should the agent loop before we force-stop it?
# This is a safety guard - without it, a confused agent could loop forever
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))


# -------------------------------------------------------
# HELPER FUNCTION: Convert MCP tool → Ollama tool format
# -------------------------------------------------------
# MCP describes tools in its own format.
# Ollama (and most LLMs) expect the OpenAI function-calling format.
# This function translates between the two.
# -------------------------------------------------------
def convert_mcp_tool_to_ollama_format(mcp_tool) -> dict:
    """
    Converts an MCP Tool object into the format Ollama expects.
    
    MCP Tool looks like:
      name: "check_ip_reputation"
      description: "Check if an IP is malicious..."
      inputSchema: { type: "object", properties: { ip_address: {...} } }
    
    Ollama wants:
      { "type": "function", "function": { "name": ..., "description": ..., "parameters": ... } }
    
    The inputSchema from MCP is already valid JSON Schema, so we can use it directly!
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description,
            # inputSchema is JSON Schema format - Ollama accepts this directly
            "parameters": mcp_tool.inputSchema
        }
    }


# -------------------------------------------------------
# HELPER FUNCTION: Print formatted output
# -------------------------------------------------------
def print_section(title: str, content: str = "", color_code: str = ""):
    """Pretty prints a section with a title bar - just for readability in the terminal."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    if content:
        print(content)


def wait_for_ollama(url: str, model: str, timeout: int = 120):
    """Wait for Ollama to be reachable and the model to be loaded before starting."""
    print(f"  Waiting for Ollama at {url} ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if any(model in m for m in models):
                    print(f"  ✓ Ollama is ready (model '{model}' available)")
                    return
                print(f"  Ollama up but model '{model}' not yet available, retrying...")
        except Exception:
            pass
        time.sleep(5)
    print(f"  ✗ Timed out waiting for Ollama after {timeout}s")
    sys.exit(1)


# ===================================================
# THE MAIN AGENT FUNCTION
# ===================================================
async def run_soc_agent(user_query: str):
    """
    The main agent loop. 
    
    This function:
    1. Connects to MCP server
    2. Discovers tools
    3. Sends query to LLM with tools available
    4. Executes tool calls the LLM requests
    5. Feeds tool results back to LLM
    6. Repeats until LLM has a final answer
    """
    
    print_section("SOC ANALYST AGENT - STARTING")
    print(f"  Model:      {MODEL}")
    print(f"  MCP Server: {MCP_SERVER_URL}")
    print(f"  Ollama:     {OLLAMA_URL}")

    # Wait for Ollama and the model to be available before proceeding
    wait_for_ollama(OLLAMA_URL, MODEL)

    # -------------------------------------------------------
    # STEP 1: Connect to MCP Server
    # -------------------------------------------------------
    # sse_client() creates an HTTP connection to our MCP server
    # It returns two stream objects (read/write) that ClientSession uses
    # -------------------------------------------------------
    print_section("STEP 1: Connecting to MCP Server")
    
    try:
        async with sse_client(MCP_SERVER_URL) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                
                # Initialize the MCP session (handshake)
                await session.initialize()
                print("  ✓ Connected to MCP server successfully")
                
                # -------------------------------------------------------
                # STEP 2: Discover available tools
                # -------------------------------------------------------
                # This is KEY to MCP - the agent doesn't have hardcoded
                # tool knowledge. It ASKS the server "what can you do?"
                # This means you can add/remove tools on the server side
                # without changing the agent code!
                # -------------------------------------------------------
                print_section("STEP 2: Discovering Tools from MCP Server")
                
                tools_response = await session.list_tools()
                mcp_tools = tools_response.tools
                
                print(f"  Found {len(mcp_tools)} tools:")
                for tool in mcp_tools:
                    print(f"    → {tool.name}: {tool.description[:60]}...")
                
                # Convert MCP tools to Ollama format
                ollama_tools = [convert_mcp_tool_to_ollama_format(t) for t in mcp_tools]
                
                # -------------------------------------------------------
                # STEP 3: Set up the conversation
                # -------------------------------------------------------
                # The "system prompt" defines the agent's role and behavior.
                # This is how you instruct the LLM to act like a SOC analyst.
                # The quality of this prompt significantly affects agent behavior!
                # -------------------------------------------------------
                print_section("STEP 3: Initializing Agent")
                
                system_prompt = """You are a skilled SOC (Security Operations Center) analyst.
Your job is to investigate security alerts and provide threat assessments.

IMPORTANT: You have tools available. You MUST call them to gather data — do NOT write out JSON or describe tool calls in text. Use the actual tool-calling mechanism provided to you.

Start by calling get_recent_alerts to see current alerts. Then for each external IP address found, call check_ip_reputation and lookup_ip_geolocation to gather threat intelligence.

Private IP ranges (10.x.x.x, 192.168.x.x, 172.16-31.x.x) are internal and generally less suspicious than external IPs.

Only after you have gathered all the data using tools, write your final threat assessment with:
- Summary of findings
- Risk level (LOW/MEDIUM/HIGH/CRITICAL) for each alert
- Recommended actions (BLOCK, MONITOR, or INVESTIGATE)

Always reference actual alert IDs and IP addresses in your analysis."""
                
                # messages is our conversation history
                # We start with the system prompt + the user's question
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_query}
                ]
                
                # Create the Ollama client pointing to our local Ollama instance
                ollama_client = ollama.Client(host=OLLAMA_URL)
                
                print(f"  ✓ Agent initialized with {len(ollama_tools)} tools available")
                print(f"\n  USER QUERY: {user_query}")
                
                # -------------------------------------------------------
                # STEP 4: THE AGENT LOOP
                # -------------------------------------------------------
                # This is the core of how agents work:
                # 
                #   LLM decides action
                #       ↓
                #   If "use a tool" → run tool → add result to conversation
                #       ↓                              ↓
                #   Loop back ←────────────────────────┘
                #       ↓
                #   If "I have enough info" → write final answer → DONE
                #
                # -------------------------------------------------------
                print_section("STEP 4: Agent Loop Running")
                
                iteration = 0  # Safety counter
                
                while iteration < MAX_ITERATIONS:
                    iteration += 1
                    print(f"\n  [Iteration {iteration}/{MAX_ITERATIONS}] Querying LLM...")
                    
                    # ── Ask the LLM what to do next ──────────────────────
                    # We send the full conversation history + available tools
                    # The LLM will either:
                    #   A) Call one or more tools (it needs more info)
                    #   B) Write a final text answer (it's done)
                    # ─────────────────────────────────────────────────────
                    response = ollama_client.chat(
                        model=MODEL,
                        messages=messages,
                        tools=ollama_tools  # The LLM sees these as options
                    )
                    
                    llm_message = response.message
                    
                    # Add the LLM's response to our conversation history
                    # (We need to track the full conversation so the LLM
                    #  has context on what it's already done)
                    messages.append({
                        "role": "assistant",
                        "content": llm_message.content or "",
                        # tool_calls will be None if the LLM isn't calling tools
                        "tool_calls": [
                            {
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in (llm_message.tool_calls or [])
                        ]
                    })
                    
                    # ── Check: is the LLM done? ───────────────────────────
                    # If there are no tool_calls, the LLM has written its
                    # final analysis. We're done!
                    # ─────────────────────────────────────────────────────
                    if not llm_message.tool_calls:
                        print("  ✓ LLM has reached a conclusion (no more tool calls)")
                        print_section("FINAL THREAT ASSESSMENT", llm_message.content)
                        return llm_message.content
                    
                    # ── Execute tool calls ────────────────────────────────
                    # The LLM wants to call tools. Let's do that through MCP.
                    # ─────────────────────────────────────────────────────
                    print(f"  LLM is calling {len(llm_message.tool_calls)} tool(s):")
                    
                    for tool_call in llm_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = tool_call.function.arguments
                        
                        # tool_args might come back as a string or dict depending
                        # on the Ollama version - normalize to dict
                        if isinstance(tool_args, str):
                            try:
                                tool_args = json.loads(tool_args)
                            except json.JSONDecodeError:
                                tool_args = {}
                        
                        print(f"\n    🔧 Tool: {tool_name}")
                        print(f"       Args: {json.dumps(tool_args, indent=8)}")
                        
                        # ── Call the tool through MCP ─────────────────────
                        # session.call_tool() sends the request to our
                        # MCP server and waits for the result
                        # ─────────────────────────────────────────────────
                        try:
                            mcp_result = await session.call_tool(tool_name, tool_args)
                            
                            # Extract the text content from the MCP response
                            # MCP returns a list of content blocks - we want text
                            if mcp_result.content and len(mcp_result.content) > 0:
                                tool_result_text = mcp_result.content[0].text
                            else:
                                tool_result_text = "Tool returned no content"
                            
                            print(f"       Result: {tool_result_text[:120]}...")
                            
                        except Exception as e:
                            tool_result_text = f"Tool execution error: {str(e)}"
                            print(f"       ERROR: {tool_result_text}")
                        
                        # ── Feed tool result back to LLM ──────────────────
                        # This is crucial - we add the tool result to the
                        # conversation so the LLM can use the information
                        # ─────────────────────────────────────────────────
                        messages.append({
                            "role": "tool",
                            "content": tool_result_text
                        })
                
                # If we hit MAX_ITERATIONS, something went wrong
                print_section("WARNING: Maximum iterations reached without conclusion")
                return "Agent reached maximum iterations without completing analysis."
    
    except ConnectionRefusedError:
        print(f"\n  ✗ ERROR: Could not connect to MCP server at {MCP_SERVER_URL}")
        print("    Is the mcp-server container running? Try: docker compose ps")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ✗ ERROR: {str(e)}")
        raise


# -------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------
# When you run this script directly, it will send a
# default SOC investigation query to the agent.
#
# Try changing this query to see different behaviors!
# -------------------------------------------------------
if __name__ == "__main__":
    
    # You can change this query to experiment with the agent
    # Try:
    #   - "Check all critical alerts and tell me if we need to block anything"
    #   - "Is IP 45.33.32.156 a threat? Investigate and report"
    #   - "Give me a summary of all high and critical alerts"
    query = (
        "Please review our recent security alerts and investigate any suspicious "
        "IP addresses. I need a threat assessment report with your recommended actions."
    )
    
    asyncio.run(run_soc_agent(query))
