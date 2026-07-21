from app.main import run_claim_agent_background
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        claim_id = sys.argv[1]
    else:
        claim_id = "38b13c64-c01e-4724-90bd-57b7a0c6030f" # use the latest claim ID
    run_claim_agent_background(claim_id)
    print("Done")
