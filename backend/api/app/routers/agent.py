from fastapi import APIRouter

from ..agent.dispatch_agent import ask_dispatch_agent
from ..models import AgentAskRequest, AgentAskResponse

router = APIRouter(prefix="/api/agent")


@router.post("/ask", response_model=AgentAskResponse)
def ask(request: AgentAskRequest) -> AgentAskResponse:
    answer = ask_dispatch_agent(request.question)
    return AgentAskResponse(answer=answer)
