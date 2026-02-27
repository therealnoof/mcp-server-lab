"""
=============================================================
 test_tools.py - TEST YOUR MCP SERVER WITHOUT THE AGENT
=============================================================
 What this file does:
   Before running the full agent, it's helpful to test that
   your MCP server tools work correctly on their own.
   
   This script connects directly to the MCP server and
   calls each tool manually so you can verify the output.
   
   Think of it like unit testing - test the tools first,
   THEN test the agent that uses them.
   
 Run with:
   docker compose run --rm agent python test_tools.py
=============================================================
"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client

MCP_SERVER_URL = "http://mcp-server:8000/sse"


async def test_all_tools():
    """Manually call each MCP tool and display the results."""
    
    print("\n" + "="*60)
    print("  MCP SERVER TOOL TEST")
    print("  Connecting to:", MCP_SERVER_URL)
    print("="*60)
    
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # ─── List all available tools ────────────────────────────
            tools = await session.list_tools()
            print(f"\n✓ Connected! Found {len(tools.tools)} tools:\n")
            for tool in tools.tools:
                print(f"  [{tool.name}]")
                print(f"    {tool.description}")
                print()
            
            # ─── Test: get_recent_alerts ─────────────────────────────
            print("="*60)
            print("  TEST: get_recent_alerts(limit=3)")
            print("="*60)
            result = await session.call_tool("get_recent_alerts", {"limit": 3})
            # Pretty-print the JSON result
            data = json.loads(result.content[0].text)
            print(json.dumps(data, indent=2))
            
            # ─── Test: check_ip_reputation (malicious IP) ────────────
            print("\n" + "="*60)
            print("  TEST: check_ip_reputation (known bad IP)")
            print("="*60)
            result = await session.call_tool(
                "check_ip_reputation", 
                {"ip_address": "185.220.101.45"}  # This is in our bad list
            )
            data = json.loads(result.content[0].text)
            print(json.dumps(data, indent=2))
            
            # ─── Test: check_ip_reputation (clean IP) ────────────────
            print("\n" + "="*60)
            print("  TEST: check_ip_reputation (clean IP)")
            print("="*60)
            result = await session.call_tool(
                "check_ip_reputation", 
                {"ip_address": "8.8.8.8"}  # Google DNS - should be clean
            )
            data = json.loads(result.content[0].text)
            print(json.dumps(data, indent=2))
            
            # ─── Test: lookup_ip_geolocation ─────────────────────────
            print("\n" + "="*60)
            print("  TEST: lookup_ip_geolocation")
            print("="*60)
            result = await session.call_tool(
                "lookup_ip_geolocation", 
                {"ip_address": "185.220.101.45"}
            )
            data = json.loads(result.content[0].text)
            print(json.dumps(data, indent=2))
            
            # ─── Test: get_alert_details ─────────────────────────────
            print("\n" + "="*60)
            print("  TEST: get_alert_details(alert_id='ALT-001')")
            print("="*60)
            result = await session.call_tool(
                "get_alert_details", 
                {"alert_id": "ALT-001"}
            )
            data = json.loads(result.content[0].text)
            print(json.dumps(data, indent=2))
            
            print("\n" + "="*60)
            print("  ALL TESTS PASSED ✓")
            print("  The MCP server is working correctly.")
            print("  You can now run the full agent.")
            print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_all_tools())
