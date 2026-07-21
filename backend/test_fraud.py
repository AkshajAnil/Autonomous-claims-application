import asyncio
import json
from app.mcp_client import McpClient

async def test_fraud():
    policy_matches = [{'text': 'foo fraud bar'}]
    visual_findings = {'consistency': 'inconsistent', 'red_flags': ['fake image']}
    amount_requested = 50000.0

    async with McpClient() as mcp:
        print("Connected.")
        decision = await mcp.call_tool("fraud_risk_score", {
            "policy_matches": policy_matches,
            "visual_findings": visual_findings,
            "amount_requested": amount_requested
        })
        print("Decision:", decision)

if __name__ == "__main__":
    asyncio.run(test_fraud())
