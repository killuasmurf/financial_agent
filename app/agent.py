from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import SystemMessage
from app.retriever import search_financial_documents
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings

# The state is now a continuous list of messages (Human, AI, and Tool results)
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

system_prompt = SystemMessage(
    content="You are a quantitative investment risk agent. Use the search tool to find historical context before answering financial queries. Cite the source file name in your response."
)

tools = [search_financial_documents]

@lru_cache(maxsize=1)
def get_react_agent():
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0,
        google_api_key=settings.GOOGLE_API_KEY,
    ).bind_tools(tools)

    def reason_node(state: AgentState):
        messages = [system_prompt] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(AgentState)
    workflow.add_node("reason_node", reason_node)
    workflow.add_node("execute_tools", ToolNode(tools=tools))
    workflow.add_edge(START, "reason_node")
    workflow.add_conditional_edges(
        "reason_node", tools_condition, {"tools": "execute_tools", END: END}
    )
    workflow.add_edge("execute_tools", "reason_node")
    return workflow.compile()