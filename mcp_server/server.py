"""
=============================================================
 PHASE 1 - MCP SERVER: SOC Tools
=============================================================
 What this file does:
   This is the MCP (Model Context Protocol) Server.
   Think of it like a "toolbox" that AI agents can reach into.
   
   We define TOOLS here. Each tool is a Python function that
   does something useful (look up an IP, check threat intel, etc.)
   
   The MCP protocol handles all the communication plumbing so
   the agent knows:
     - What tools exist
     - What arguments each tool needs
     - How to call them and get results back
   
 Transport: SSE (Server-Sent Events) over HTTP
   This means the server runs as a web service, which is great
   for Docker because each container can talk to it over the network.
=============================================================
"""

import json
import httpx
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP

# -------------------------------------------------------
# Create the MCP server instance
# "SOC Tools Server" is just a human-readable name
# -------------------------------------------------------
mcp = FastMCP("SOC Tools Server")


# -------------------------------------------------------
# THREAT INTEL DATABASE (simulated for the lab)
# -------------------------------------------------------
# In a real SOC, this would connect to feeds like:
#   VirusTotal, AbuseIPDB, Emerging Threats, etc.
# For the lab we use a hardcoded list of known-bad IPs.
#
# Format: "ip": {"threat": "description", "confidence": 0-100}
# -------------------------------------------------------
KNOWN_MALICIOUS_IPS = {
    "185.220.101.45": {"threat": "Tor Exit Node",       "confidence": 90},
    "192.42.116.16":  {"threat": "Port Scanning",       "confidence": 75},
    "45.33.32.156":   {"threat": "Known C2 Server",     "confidence": 88},
    "198.199.10.1":   {"threat": "Brute Force Source",  "confidence": 72},
    "89.248.167.131": {"threat": "Malware Distribution","confidence": 95},
}

# -------------------------------------------------------
# SIMULATED ALERT LOG
# -------------------------------------------------------
# In a real environment this would come from a SIEM like
# Splunk, Microsoft Sentinel, or Elastic.
# For the lab, we hardcode some realistic-looking alerts.
# -------------------------------------------------------
SIMULATED_ALERTS = [
    {
        "id": "ALT-001",
        "timestamp": "2024-01-15T10:23:00Z",
        "source_ip": "185.220.101.45",
        "destination_ip": "10.0.1.22",
        "event_type": "SSH Brute Force",
        "severity": "HIGH",
        "attempts": 847
    },
    {
        "id": "ALT-002",
        "timestamp": "2024-01-15T10:25:00Z",
        "source_ip": "192.168.1.105",   # internal IP - less suspicious
        "destination_ip": "10.0.1.5",
        "event_type": "Port Scan",
        "severity": "MEDIUM",
        "attempts": 12
    },
    {
        "id": "ALT-003",
        "timestamp": "2024-01-15T10:27:00Z",
        "source_ip": "45.33.32.156",
        "destination_ip": "10.0.1.44",
        "event_type": "Suspicious Outbound Connection",
        "severity": "HIGH",
        "attempts": 3
    },
    {
        "id": "ALT-004",
        "timestamp": "2024-01-15T10:30:00Z",
        "source_ip": "10.0.0.52",       # internal IP
        "destination_ip": "8.8.8.8",
        "event_type": "Unusual DNS Volume",
        "severity": "MEDIUM",
        "attempts": 1203
    },
    {
        "id": "ALT-005",
        "timestamp": "2024-01-15T10:31:00Z",
        "source_ip": "89.248.167.131",
        "destination_ip": "10.0.1.10",
        "event_type": "Possible Data Exfiltration",
        "severity": "CRITICAL",
        "attempts": 1
    },
]


# ===================================================
# TOOL DEFINITIONS
# ===================================================
# The @mcp.tool() decorator registers this function
# as a tool that AI agents can discover and call.
#
# The docstring IS IMPORTANT - the AI agent reads
# the docstring to understand what the tool does
# and when to use it. Write clear docstrings!
# ===================================================

@mcp.tool()
async def get_recent_alerts(limit: int = 5) -> str:
    """
    Retrieve recent security alerts from the SOC log store.
    Use this tool first to see what security events need investigation.
    Returns a list of alerts including source IPs, event types, and severity.
    
    Args:
        limit: How many recent alerts to return (default: 5, max: 10)
    """
    # Cap the limit so we don't return too much data
    limit = min(limit, 10)
    
    alerts_to_return = SIMULATED_ALERTS[:limit]
    
    # We return JSON strings - structured data the agent can parse
    return json.dumps({
        "alert_count": len(alerts_to_return),
        "alerts": alerts_to_return
    }, indent=2)


@mcp.tool()
async def lookup_ip_geolocation(ip_address: str) -> str:
    """
    Look up geographic and network ownership information for an IP address.
    This provides context about WHERE an IP is located and WHO owns it.
    Useful for identifying if traffic is coming from unexpected countries
    or suspicious hosting providers.
    
    Args:
        ip_address: The IPv4 address to look up (e.g., '185.220.101.45')
    
    Returns:
        Country, city, ISP, and organization details for the IP.
    """
    # ip-api.com is a free service - no API key needed for the lab
    # Rate limit: 45 requests/minute on the free tier
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://ip-api.com/json/{ip_address}",
                params={"fields": "status,country,regionName,city,isp,org,as,query"}
            )
            data = response.json()
        
        # ip-api.com returns "fail" status for private/reserved IPs
        if data.get("status") == "fail":
            return json.dumps({
                "ip": ip_address,
                "error": "Could not geolocate IP - may be private/reserved range",
                "is_private": True
            }, indent=2)
        
        return json.dumps({
            "ip": ip_address,
            "country": data.get("country", "Unknown"),
            "region": data.get("regionName", "Unknown"),
            "city": data.get("city", "Unknown"),
            "isp": data.get("isp", "Unknown"),
            "organization": data.get("org", "Unknown"),
            "asn": data.get("as", "Unknown"),
            "queried_at": datetime.now(timezone.utc).isoformat()
        }, indent=2)
    
    except Exception as e:
        return json.dumps({"error": f"Geolocation lookup failed: {str(e)}"}, indent=2)


@mcp.tool()
async def check_ip_reputation(ip_address: str) -> str:
    """
    Check if an IP address is known to be malicious based on threat intelligence feeds.
    This tool should be called for ANY external IP addresses found in alerts.
    Returns whether the IP is known-bad, the threat category, and a confidence score.
    
    Args:
        ip_address: The IPv4 address to check (e.g., '185.220.101.45')
    
    Returns:
        Threat status including is_malicious flag, threat type, and confidence score (0-100).
    """
    if ip_address in KNOWN_MALICIOUS_IPS:
        threat_info = KNOWN_MALICIOUS_IPS[ip_address]
        return json.dumps({
            "ip": ip_address,
            "is_malicious": True,
            "threat_type": threat_info["threat"],
            "confidence_score": threat_info["confidence"],
            "recommendation": "BLOCK - High confidence threat indicator",
            "checked_at": datetime.now(timezone.utc).isoformat()
        }, indent=2)
    
    # IP not in our threat list - treat as clean (for lab purposes)
    return json.dumps({
        "ip": ip_address,
        "is_malicious": False,
        "threat_type": "None detected",
        "confidence_score": 0,
        "recommendation": "MONITOR - No known threat indicators",
        "checked_at": datetime.now(timezone.utc).isoformat()
    }, indent=2)


@mcp.tool()
async def get_alert_details(alert_id: str) -> str:
    """
    Get detailed information about a specific alert by its ID.
    Use this when you need more context about a particular security event.
    
    Args:
        alert_id: The alert identifier (e.g., 'ALT-001')
    
    Returns:
        Full details of the specified alert.
    """
    for alert in SIMULATED_ALERTS:
        if alert["id"] == alert_id:
            return json.dumps(alert, indent=2)
    
    return json.dumps({"error": f"Alert {alert_id} not found"}, indent=2)


# -------------------------------------------------------
# START THE SERVER
# -------------------------------------------------------
# When this script is run directly (not imported),
# start the MCP server with SSE transport.
# SSE (Server-Sent Events) lets the server run as
# an HTTP web service on port 8000.
# -------------------------------------------------------
if __name__ == "__main__":
    print("Starting SOC Tools MCP Server on port 8000...")
    print("Available tools: get_recent_alerts, lookup_ip_geolocation,")
    print("                 check_ip_reputation, get_alert_details")
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
