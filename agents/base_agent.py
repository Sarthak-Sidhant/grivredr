"""
Base Agent Class with Reflection and Cost Tracking
All specialized agents inherit from this
"""
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from config.ai_client import ai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    WORKING = "working"
    REFLECTING = "reflecting"
    WAITING_HUMAN = "waiting_human"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AgentAction:
    """Records a single agent action"""
    timestamp: datetime
    action_type: str
    description: str
    result: Any
    success: bool
    cost: float = 0.0
    tokens_used: int = 0


@dataclass
class AgentAttempt:
    """Records one complete attempt"""
    attempt_number: int
    actions: List[AgentAction] = field(default_factory=list)
    strategy: str = ""
    outcome: str = ""
    success: bool = False
    total_cost: float = 0.0


class CostTracker:
    """Tracks API costs in real-time"""

    # Model costs per 1M tokens (input/output)
    COSTS = {
        "claude-haiku-4-5-20251001": (1.00, 5.00),
        "claude-sonnet-4-5-20250929": (3.00, 15.00),
        "claude-opus-4-5-20251101": (5.00, 25.00),
    }

    def __init__(self):
        self.total_cost = 0.0
        self.calls_by_model = {}
        self.calls_by_agent = {}

    def track_call(self, model: str, input_tokens: int, output_tokens: int, agent_name: str) -> float:
        """Calculate and track cost of an API call"""
        if model not in self.COSTS:
            logger.warning(f"Unknown model: {model}")
            return 0.0

        input_cost_per_m, output_cost_per_m = self.COSTS[model]

        cost = (input_tokens / 1_000_000 * input_cost_per_m +
                output_tokens / 1_000_000 * output_cost_per_m)

        self.total_cost += cost

        # Track by model
        if model not in self.calls_by_model:
            self.calls_by_model[model] = {"count": 0, "cost": 0.0, "tokens": 0}
        self.calls_by_model[model]["count"] += 1
        self.calls_by_model[model]["cost"] += cost
        self.calls_by_model[model]["tokens"] += input_tokens + output_tokens

        # Track by agent
        if agent_name not in self.calls_by_agent:
            self.calls_by_agent[agent_name] = {"count": 0, "cost": 0.0}
        self.calls_by_agent[agent_name]["count"] += 1
        self.calls_by_agent[agent_name]["cost"] += cost

        logger.info(f"💰 Cost: ${cost:.4f} | Model: {model} | Agent: {agent_name}")

        return cost


# Global cost tracker instance
cost_tracker = CostTracker()


class BaseAgent(ABC):
    """
    Base class for all agents with built-in reflection and cost tracking
    """

    def __init__(self, name: str, max_attempts: int = 3):
        self.name = name
        self.max_attempts = max_attempts
        self.status = AgentStatus.IDLE
        self.attempts: List[AgentAttempt] = []
        self.current_attempt: Optional[AgentAttempt] = None
        self.knowledge: Dict[str, Any] = {}  # Learned patterns

        # Callbacks for monitoring
        self.on_status_change = None
        self.on_action = None
        self.on_reflection = None
        self.on_human_needed = None

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution loop with reflection
        """
        logger.info(f"🤖 [{self.name}] Starting task: {task.get('description', 'N/A')}")

        for attempt_num in range(1, self.max_attempts + 1):
            self.current_attempt = AgentAttempt(
                attempt_number=attempt_num,
                strategy=await self._plan_strategy(task, attempt_num)
            )

            self._set_status(AgentStatus.WORKING)

            try:
                # Execute the agent's specific logic
                result = await self._execute_attempt(task)

                # Record success
                self.current_attempt.success = result.get("success", False)
                self.current_attempt.outcome = result.get("message", "")
                self.current_attempt.total_cost = sum(a.cost for a in self.current_attempt.actions)

                self.attempts.append(self.current_attempt)

                if result.get("success"):
                    self._set_status(AgentStatus.SUCCESS)
                    logger.info(f"✅ [{self.name}] Success on attempt {attempt_num}")
                    return result

                # Failed, reflect
                self._set_status(AgentStatus.REFLECTING)
                reflection = await self._reflect_on_failure(result)

                if self._trigger_reflection(reflection):
                    logger.info(f"🤔 [{self.name}] Reflecting: {reflection['reasoning']}")

                if attempt_num < self.max_attempts:
                    logger.info(f"🔄 [{self.name}] Retrying... ({attempt_num + 1}/{self.max_attempts})")
                    await asyncio.sleep(2)  # Brief pause
                else:
                    # Max attempts reached, ask human
                    self._set_status(AgentStatus.WAITING_HUMAN)
                    human_input = await self._request_human_help(task, reflection)

                    if human_input.get("continue"):
                        # Human provided guidance, try once more
                        self.max_attempts += 1
                        task.update(human_input.get("hints", {}))
                        continue
                    else:
                        break

            except Exception as e:
                logger.error(f"❌ [{self.name}] Error: {e}")
                self.current_attempt.success = False
                self.current_attempt.outcome = str(e)
                self.attempts.append(self.current_attempt)

        self._set_status(AgentStatus.FAILED)
        return {
            "success": False,
            "error": "Max attempts reached",
            "attempts": len(self.attempts),
            "total_cost": sum(a.total_cost for a in self.attempts)
        }

    async def _plan_strategy(self, task: Dict[str, Any], attempt_num: int) -> str:
        """
        Plan strategy for this attempt
        """
        if attempt_num == 1:
            return "Initial exploration with standard approach"

        # Use Claude to suggest strategy based on previous failures
        previous_attempts = [
            {
                "attempt": a.attempt_number,
                "strategy": a.strategy,
                "outcome": a.outcome,
                "success": a.success
            }
            for a in self.attempts
        ]

        prompt = f"""You are a strategic AI agent planner for {self.name}.

Previous attempts failed:
{previous_attempts}

Task: {task}

Based on the failures, suggest a new strategy. Be specific and actionable.
Return JSON: {{"strategy": "description", "key_changes": ["change1", "change2"]}}
"""

        start_time = time.time()
        response = ai_client.client.messages.create(
            model=ai_client.models["balanced"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        elapsed = time.time() - start_time

        # Track cost
        usage = response.usage
        cost = cost_tracker.track_call(
            model=ai_client.models["balanced"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=self.name
        )

        strategy_response = response.content[0].text

        # Record this as an action
        action = AgentAction(
            timestamp=datetime.now(),
            action_type="plan_strategy",
            description=f"Planning strategy for attempt {attempt_num}",
            result=strategy_response,
            success=True,
            cost=cost,
            tokens_used=usage.input_tokens + usage.output_tokens
        )
        self.current_attempt.actions.append(action)

        logger.info(f"📋 [{self.name}] Strategy: {strategy_response[:100]}...")

        return strategy_response

    @abstractmethod
    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implement the agent's specific logic
        Must return: {"success": bool, "message": str, ...}
        """
        pass

    async def _reflect_on_failure(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use Claude to reflect on why we failed
        """
        prompt = f"""You are a reflective AI agent: {self.name}.

Your attempt failed with this result:
{result}

Your actions were:
{[{"action": a.action_type, "result": a.result, "success": a.success} for a in self.current_attempt.actions]}

Analyze:
1. Why did this fail?
2. What assumptions were wrong?
3. What should I try differently?

Return JSON: {{
    "failure_reason": "why it failed",
    "wrong_assumptions": ["assumption1", ...],
    "next_approach": "what to try",
    "reasoning": "your thinking process"
}}
"""

        start_time = time.time()
        response = ai_client.client.messages.create(
            model=ai_client.models["balanced"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800
        )

        usage = response.usage
        cost = cost_tracker.track_call(
            model=ai_client.models["balanced"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=f"{self.name}_reflection"
        )

        reflection = response.content[0].text

        if self.on_reflection:
            await self.on_reflection(self.name, reflection)

        return {"reflection": reflection, "cost": cost}

    async def _request_human_help(self, task: Dict[str, Any], reflection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request human intervention
        """
        logger.warning(f"🙋 [{self.name}] Requesting human help after {len(self.attempts)} attempts")

        if self.on_human_needed:
            return await self.on_human_needed(self.name, task, reflection, self.attempts)

        # Default: no human available, return failure
        return {"continue": False}

    def _record_action(
        self,
        action_type: str,
        description: str,
        result: Any,
        success: bool,
        cost: float = 0.0,
        tokens: int = 0
    ):
        """Record an action taken by the agent"""
        action = AgentAction(
            timestamp=datetime.now(),
            action_type=action_type,
            description=description,
            result=result,
            success=success,
            cost=cost,
            tokens_used=tokens
        )

        if self.current_attempt:
            self.current_attempt.actions.append(action)

        if self.on_action:
            # Wrap callback in error handler to avoid lost exceptions
            async def safe_callback():
                try:
                    await self.on_action(self.name, action)
                except Exception as e:
                    logger.error(f"Callback error in on_action: {e}")
            asyncio.create_task(safe_callback())

    def _set_status(self, status: AgentStatus):
        """Update agent status"""
        self.status = status
        if self.on_status_change:
            # Wrap callback in error handler
            async def safe_callback():
                try:
                    await self.on_status_change(self.name, status)
                except Exception as e:
                    logger.error(f"Callback error in on_status_change: {e}")
            asyncio.create_task(safe_callback())

    def _trigger_reflection(self, reflection: Dict[str, Any]) -> bool:
        """Notify listeners about reflection"""
        return self.on_reflection is not None

    def get_total_cost(self) -> float:
        """Get total cost of all attempts"""
        return sum(a.total_cost for a in self.attempts)

    def get_stats(self) -> Dict[str, Any]:
        """Get agent execution statistics"""
        return {
            "name": self.name,
            "status": self.status.value,
            "total_attempts": len(self.attempts),
            "successful_attempts": sum(1 for a in self.attempts if a.success),
            "total_cost": self.get_total_cost(),
            "total_actions": sum(len(a.actions) for a in self.attempts)
        }
