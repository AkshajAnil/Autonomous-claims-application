import asyncio
import traceback
import sys
from app.database import SessionLocal
from app.agent import run_claim_agent

async def main():
    if len(sys.argv) > 1:
        claim_id = sys.argv[1]
    else:
        claim_id = "3d212930-6127-4c45-a894-ad3cab1feb12"
        
    print(f"Running agent synchronously for claim {claim_id}...")
    db = SessionLocal()
    try:
        # We manually run the code inside run_claim_agent but without the broad try-except block
        # so we can see the exact traceback!
        from app.mcp_client import McpClient
        from app.repository import claim_with_children, mark_processing
        
        claim = claim_with_children(db, claim_id)
        if not claim:
            print("Claim not found!")
            return
            
        async with McpClient() as mcp:
            print("Connected to MCP server.")
            policy_matches = await mcp.call_tool(
                "policy_rag_search",
                {"query": f"{claim.claim_type}: {claim.description}", "limit": 3},
            )
            print("Policy search success:", policy_matches)

            image_urls = [e.url for e in claim.evidence]
            print("Image URLs:", image_urls)
            visual_findings = await mcp.call_tool(
                "visual_damage_assessment",
                {"claim_description": claim.description, "image_urls": image_urls},
            )
            print("Visual findings success:", visual_findings)
    except Exception as e:
        print("\n--- Exception Caught ---")
        print(type(e), e)
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
