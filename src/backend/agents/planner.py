import json
import logging
import uuid
from typing import List, Optional

from autogen_core import MessageContext, RoutedAgent, default_subscription, message_handler
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_core.models import LLMMessage, UserMessage
from pydantic import BaseModel

from context.cosmos_memory import CosmosBufferedChatCompletionContext
from models.messages import (
    AgentMessage,
    HumanClarification,
    BAgentType,
    InputTask,
    Plan,
    PlanStatus,
    Step,
    StepStatus,
    HumanFeedbackStatus,
)
from event_utils import track_event_if_configured


@default_subscription
class PlannerAgent(RoutedAgent):
    def __init__(
        self,
        model_client: AzureOpenAIChatCompletionClient,
        session_id: str,
        user_id: str,
        memory: CosmosBufferedChatCompletionContext,
        available_agents: List[BAgentType],
        agent_tools_list: List[str] = None,
    ):
        super().__init__("PlannerAgent")
        self._model_client = model_client
        self._session_id = session_id
        self._user_id = user_id
        self._memory = memory
        self._available_agents = available_agents
        self._agent_tools_list = agent_tools_list or []

    @message_handler
    async def handle_input_task(self, message: InputTask, ctx: MessageContext) -> Plan:
        instruction = self._generate_instruction(message.description)
        plan, steps = await self._create_structured_plan(
            [UserMessage(content=instruction, source="PlannerAgent")]
        )

        await self._memory.add_item(AgentMessage(
            session_id=message.session_id,
            user_id=self._user_id,
            plan_id=plan.id,
            content=f"Generated a plan with {len(steps)} steps.",
            source="PlannerAgent",
            step_id="",
        ))

        if plan.human_clarification_request:
            await self._memory.add_item(AgentMessage(
                session_id=message.session_id,
                user_id=self._user_id,
                plan_id=plan.id,
                content=f"I require additional info: {plan.human_clarification_request}",
                source="PlannerAgent",
                step_id="",
            ))

        return plan

    def _generate_instruction(self, objective: str) -> str:
        agents = ", ".join(str(agent) for agent in self._available_agents)

        # This handles both strings and dicts with a 'name' key
        tools = ", ".join(
            tool["name"] if isinstance(tool, dict) and "name" in tool else str(tool)
            for tool in (self._agent_tools_list or [])
        )

        return f"""
        You are the Planner, an AI orchestrator that manages a group of AI agents to accomplish tasks.

        Your goal is to decompose the following objective into a concise plan of action with up to 10 steps. Each step should be assigned to one of the available agents and specify exactly what to do.

        Return the response strictly in the following JSON format, and nothing else:

        {{
        "initial_goal": "<repeat the objective here>",
        "steps": [
            {{
            "action": "<short sentence, what the agent should do>",
            "agent": "<agent name (must be one of: HumanAgent, GenericAgent, EarningCallsAnalystAgent, CompanyAnalystAgent, SecAnalystAgent, TechnicalAnalysisAgent)>"
            }}
        ],
        "summary_plan_and_steps": "<a short summary under 50 words>",
        "human_clarification_request": "<optional: ask a question to clarify if needed, else null>"
        }}

        Do not include commentary or explanations outside the JSON.

        ---

        The objective is:
        {objective}

        The available agents are:
        {agents}

        The available functions are:
        {tools}
        """

    async def _create_structured_plan(self, messages: List[LLMMessage]) -> tuple[Plan, list]:
        class StructuredOutputStep(BaseModel):
            action: str
            agent: BAgentType

        class StructuredOutputPlan(BaseModel):
            initial_goal: str
            steps: List[StructuredOutputStep]
            summary_plan_and_steps: str
            human_clarification_request: Optional[str] = None

        try:
            # Safe: no structured_output param
            result = await self._model_client.create(
                messages,
                extra_create_args={"temperature": 0.3},
            )
            content = result.content

            # Log for debug
            logging.info("LLM Response:\n%s", content)

            # Fix: remove markdown code block if present
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()

            parsed_result = json.loads(cleaned)
            structured_plan = StructuredOutputPlan(**parsed_result)

            plan = Plan(
                id=str(uuid.uuid4()),
                session_id=self._session_id,
                user_id=self._user_id,
                initial_goal=structured_plan.initial_goal,
                overall_status=PlanStatus.in_progress,
                source="PlannerAgent",
                summary=structured_plan.summary_plan_and_steps,
                human_clarification_request=structured_plan.human_clarification_request,
            )
            await self._memory.add_plan(plan)

            steps = []
            for step_data in structured_plan.steps:
                step = Step(
                    plan_id=plan.id,
                    action=step_data.action,
                    agent=step_data.agent,
                    status=StepStatus.planned,
                    session_id=self._session_id,
                    user_id=self._user_id,
                    human_approval_status=HumanFeedbackStatus.requested,
                )
                await self._memory.add_step(step)
                steps.append(step)

            return plan, steps

        except Exception as e:
            logging.error(f"PlannerAgent: Failed to generate structured plan: {e}")
            plan = Plan(
                id=str(uuid.uuid4()),
                session_id=self._session_id,
                user_id=self._user_id,
                initial_goal="Error generating plan",
                overall_status=PlanStatus.failed,
                source="PlannerAgent",
                summary="No valid steps were generated.",
            )
            return plan, []
