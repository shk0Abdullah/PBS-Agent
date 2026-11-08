from fastapi import FastAPI
from pydantic import BaseModel, Field

from tds.agent.service import UrduSQLAgent
from tds.agent.evaluation import run_evaluation

app = FastAPI(
    title="Verified Urdu Text-to-SQL Agent",
    description="Auditable Urdu/Roman Urdu queries over Pakistan Bureau of Statistics education data.",
    version="0.2.0"
)

class AskRequest(BaseModel):
    question: str = Field(min_length=2, examples=["Punjab mein school se bahar bachay kitne hain?"])
    include_chart: bool = False

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "dataset": "PBS Education Table 1", "verification": "enabled"}


@app.post("/ask")
def ask(request: AskRequest):
    """Plan, verify, execute, and explain a constrained Urdu/Roman Urdu query."""
    # SQLite in-memory connections are thread-affine. FastAPI executes sync
    # routes in a worker thread, so each request receives its own small,
    # read-only analytical database rather than sharing a startup connection.
    return UrduSQLAgent().ask(request.question, request.include_chart)


@app.get("/evaluation")
def evaluation():
    """Run the gold-SQL and safety evaluation suite."""
    return run_evaluation()
