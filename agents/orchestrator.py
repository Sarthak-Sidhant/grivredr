"""
Orchestrator - Coordinates all agents in the training workflow
Manages human-in-the-loop interactions and knowledge base updates
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from agents.base_agent import cost_tracker
from agents.form_discovery_agent import FormDiscoveryAgent
from agents.test_agent import TestValidationAgent
from agents.js_analyzer_agent import JavaScriptAnalyzerAgent
from agents.code_generator_agent import CodeGeneratorAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrainingSession:
    """Represents a complete training session"""
    session_id: str
    municipality: str
    url: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "in_progress"  # in_progress, completed, failed, waiting_human

    # Agent results
    discovery_result: Optional[Dict[str, Any]] = None
    js_analysis_result: Optional[Dict[str, Any]] = None
    test_result: Optional[Dict[str, Any]] = None
    code_gen_result: Optional[Dict[str, Any]] = None

    # Metrics
    total_cost: float = 0.0
    human_interventions: int = 0
    agent_attempts: Dict[str, int] = field(default_factory=dict)

    # Human feedback
    human_corrections: list = field(default_factory=list)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "municipality": self.municipality,
            "url": self.url,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time) if self.end_time else None,
            "status": self.status,
            "total_cost": self.total_cost,
            "human_interventions": self.human_interventions,
            "agent_attempts": self.agent_attempts
        }


class Orchestrator:
    """
    Main coordinator for the AI agent training system
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.sessions: Dict[str, TrainingSession] = {}
        self.active_session: Optional[TrainingSession] = None

        # Callbacks for UI updates
        self.on_status_update: Optional[Callable] = None
        self.on_agent_action: Optional[Callable] = None
        self.on_human_needed: Optional[Callable] = None
        self.on_cost_update: Optional[Callable] = None

        # Results directory
        self.results_dir = Path("training_sessions")
        self.results_dir.mkdir(exist_ok=True)

    async def train_municipality(
        self,
        url: str,
        municipality: str,
        hints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main training workflow - coordinates all agents

        Args:
            url: URL of the grievance form
            municipality: Municipality name
            hints: Optional hints from human (for retries)

        Returns:
            Complete training result
        """
        # Create training session
        session_id = f"{municipality}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session = TrainingSession(
            session_id=session_id,
            municipality=municipality,
            url=url,
            start_time=datetime.now()
        )

        self.sessions[session_id] = session
        self.active_session = session

        logger.info(f"🎯 Starting training session: {session_id}")
        logger.info(f"   Municipality: {municipality}")
        logger.info(f"   URL: {url}")

        try:
            # Phase 1: Form Discovery
            logger.info("\n" + "="*80)
            logger.info("PHASE 1: FORM DISCOVERY")
            logger.info("="*80)

            discovery_result = await self._run_form_discovery(session, url, municipality, hints)

            if not discovery_result["success"]:
                return await self._handle_failure(session, "form_discovery", discovery_result)

            session.discovery_result = discovery_result

            # Phase 2: JavaScript Analysis
            logger.info("\n" + "="*80)
            logger.info("PHASE 2: JAVASCRIPT ANALYSIS")
            logger.info("="*80)

            js_result = await self._run_js_analysis(session, url)
            session.js_analysis_result = js_result

            # Phase 3: Test Validation
            logger.info("\n" + "="*80)
            logger.info("PHASE 3: TEST VALIDATION")
            logger.info("="*80)

            test_result = await self._run_validation_tests(session)

            if not test_result["success"] or test_result.get("needs_review"):
                return await self._request_human_review(session, test_result)

            session.test_result = test_result

            # Phase 4: Code Generation
            logger.info("\n" + "="*80)
            logger.info("PHASE 4: CODE GENERATION")
            logger.info("="*80)

            code_result = await self._run_code_generation(session)

            if not code_result["success"]:
                return await self._handle_failure(session, "code_generation", code_result)

            session.code_gen_result = code_result

            # Phase 5: Finalize
            logger.info("\n" + "="*80)
            logger.info("TRAINING COMPLETE!")
            logger.info("="*80)

            return await self._finalize_session(session)

        except Exception as e:
            logger.error(f"❌ Training session failed: {e}")
            session.status = "failed"
            session.end_time = datetime.now()
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e)
            }

    async def _run_form_discovery(
        self,
        session: TrainingSession,
        url: str,
        municipality: str,
        hints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Phase 1: Run form discovery agent"""

        agent = FormDiscoveryAgent(headless=self.headless)

        # Set up callbacks
        agent.on_status_change = self._agent_status_callback
        agent.on_action = self._agent_action_callback
        agent.on_human_needed = self._human_needed_callback

        task = {
            "url": url,
            "municipality": municipality,
            "hints": hints or {}
        }

        result = await agent.execute(task)

        session.agent_attempts["discovery"] = len(agent.attempts)
        session.total_cost += agent.get_total_cost()

        return result

    async def _run_js_analysis(
        self,
        session: TrainingSession,
        url: str
    ) -> Dict[str, Any]:
        """Phase 2: Run JavaScript analysis agent"""

        agent = JavaScriptAnalyzerAgent(headless=self.headless)

        agent.on_status_change = self._agent_status_callback
        agent.on_action = self._agent_action_callback

        task = {
            "url": url,
            "schema": session.discovery_result.get("schema")
        }

        result = await agent.execute(task)

        session.agent_attempts["js_analysis"] = len(agent.attempts)
        session.total_cost += agent.get_total_cost()

        return result

    async def _run_validation_tests(
        self,
        session: TrainingSession
    ) -> Dict[str, Any]:
        """Phase 3: Run test validation agent"""

        agent = TestValidationAgent(headless=self.headless)

        agent.on_status_change = self._agent_status_callback
        agent.on_action = self._agent_action_callback

        task = {
            "schema": session.discovery_result.get("schema")
        }

        result = await agent.execute(task)

        session.agent_attempts["testing"] = len(agent.attempts)
        session.total_cost += agent.get_total_cost()

        return result

    async def _run_code_generation(
        self,
        session: TrainingSession
    ) -> Dict[str, Any]:
        """Phase 4: Run code generator agent"""

        agent = CodeGeneratorAgent()

        agent.on_status_change = self._agent_status_callback
        agent.on_action = self._agent_action_callback

        task = {
            "schema": session.discovery_result.get("schema"),
            "js_analysis": session.js_analysis_result.get("analysis", {}),
            "test_results": session.test_result.get("results", {})
        }

        result = await agent.execute(task)

        session.agent_attempts["code_generation"] = len(agent.attempts)
        session.total_cost += agent.get_total_cost()

        return result

    async def _handle_failure(
        self,
        session: TrainingSession,
        phase: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle agent failure - may request human intervention"""

        logger.warning(f"⚠️  Phase {phase} failed or needs review")

        session.status = "waiting_human"

        if self.on_human_needed:
            human_response = await self.on_human_needed(
                session_id=session.session_id,
                phase=phase,
                failure_info=result
            )

            if human_response.get("continue"):
                # Human provided guidance, retry
                session.human_interventions += 1
                session.human_corrections.append({
                    "phase": phase,
                    "feedback": human_response.get("feedback"),
                    "hints": human_response.get("hints")
                })

                # Retry the training with hints
                return await self.train_municipality(
                    url=session.url,
                    municipality=session.municipality,
                    hints=human_response.get("hints")
                )
            else:
                # Human aborted
                session.status = "aborted"
                session.end_time = datetime.now()
                return {
                    "success": False,
                    "session_id": session.session_id,
                    "status": "aborted_by_human",
                    "message": "Training aborted by human"
                }

        # No human callback, just fail
        session.status = "failed"
        session.end_time = datetime.now()
        return {
            "success": False,
            "session_id": session.session_id,
            "phase_failed": phase,
            "reason": result.get("message", "Unknown")
        }

    async def _request_human_review(
        self,
        session: TrainingSession,
        test_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request human to review and approve the form schema"""

        logger.info("🙋 Requesting human review...")

        session.status = "waiting_human"

        if self.on_human_needed:
            review_data = {
                "session_id": session.session_id,
                "schema": session.discovery_result.get("schema"),
                "test_results": test_result,
                "js_analysis": session.js_analysis_result.get("analysis"),
                "total_cost_so_far": session.total_cost
            }

            human_response = await self.on_human_needed(
                session_id=session.session_id,
                phase="human_review",
                failure_info=review_data
            )

            if human_response.get("approved"):
                logger.info("✅ Human approved, continuing to code generation...")
                session.status = "in_progress"
                session.human_interventions += 1

                # Update schema with human corrections if any
                if human_response.get("corrections"):
                    session.discovery_result["schema"] = human_response["corrections"]

                # Continue to code generation
                code_result = await self._run_code_generation(session)
                session.code_gen_result = code_result

                return await self._finalize_session(session)
            else:
                logger.info("❌ Human rejected, aborting")
                session.status = "rejected"
                session.end_time = datetime.now()
                return {
                    "success": False,
                    "session_id": session.session_id,
                    "status": "rejected_by_human"
                }

        # No human available, proceed with caution
        logger.warning("⚠️ No human available for review, proceeding anyway")
        code_result = await self._run_code_generation(session)
        session.code_gen_result = code_result
        return await self._finalize_session(session)

    async def _finalize_session(self, session: TrainingSession) -> Dict[str, Any]:
        """Finalize training session and save results"""

        session.status = "completed"
        session.end_time = datetime.now()

        # Calculate final cost from global tracker
        session.total_cost = cost_tracker.total_cost

        # Save session to file
        session_file = self.results_dir / f"{session.session_id}.json"
        with open(session_file, "w") as f:
            json.dump(session.to_dict(), f, indent=2, default=str)

        logger.info(f"\n{'='*80}")
        logger.info(f"🎉 TRAINING SESSION COMPLETED!")
        logger.info(f"{'='*80}")
        logger.info(f"Session ID: {session.session_id}")
        logger.info(f"Municipality: {session.municipality}")
        logger.info(f"Total Cost: ${session.total_cost:.4f}")
        logger.info(f"Human Interventions: {session.human_interventions}")
        logger.info(f"Duration: {(session.end_time - session.start_time).total_seconds():.1f}s")

        if session.code_gen_result:
            logger.info(f"Scraper: {session.code_gen_result.get('scraper', {}).get('file_path')}")

        logger.info(f"Session saved: {session_file}")
        logger.info(f"{'='*80}\n")

        return {
            "success": True,
            "session_id": session.session_id,
            "municipality": session.municipality,
            "scraper_path": session.code_gen_result.get("scraper", {}).get("file_path"),
            "total_cost": session.total_cost,
            "human_interventions": session.human_interventions,
            "session_file": str(session_file)
        }

    # Callback methods for agent status updates

    async def _agent_status_callback(self, agent_name: str, status):
        """Called when an agent changes status"""
        if self.on_status_update:
            await self.on_status_update(agent_name, status.value)

    async def _agent_action_callback(self, agent_name: str, action):
        """Called when an agent takes an action"""
        if self.on_agent_action:
            await self.on_agent_action(agent_name, {
                "type": action.action_type,
                "description": action.description,
                "result": str(action.result)[:200],
                "cost": action.cost
            })

    async def _human_needed_callback(
        self,
        agent_name: str,
        task: Dict[str, Any],
        reflection: Dict[str, Any],
        attempts: list
    ) -> Dict[str, Any]:
        """Called when an agent needs human help"""
        logger.warning(f"\n🙋 [{agent_name}] Requesting human intervention")
        logger.warning(f"   Attempts: {len(attempts)}")
        logger.warning(f"   Reflection: {reflection.get('reflection', 'N/A')[:200]}")

        if self.on_human_needed:
            return await self.on_human_needed(
                session_id=self.active_session.session_id if self.active_session else "unknown",
                phase=f"agent_{agent_name}",
                failure_info={
                    "agent": agent_name,
                    "task": task,
                    "reflection": reflection,
                    "attempts": len(attempts)
                }
            )

        # Default: no human available, fail
        return {"continue": False}

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a training session"""
        session = self.sessions.get(session_id)
        if session:
            return session.to_dict()
        return None

    def get_cost_breakdown(self) -> Dict[str, Any]:
        """Get detailed cost breakdown"""
        return {
            "total_cost": cost_tracker.total_cost,
            "by_model": cost_tracker.calls_by_model,
            "by_agent": cost_tracker.calls_by_agent
        }


# For testing
async def test_orchestrator():
    """Test the orchestrator"""

    orchestrator = Orchestrator(headless=False)

    result = await orchestrator.train_municipality(
        url="https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
        municipality="ranchi_smart_test"
    )

    print("\n" + "="*80)
    print("FINAL RESULT")
    print("="*80)
    print(json.dumps(result, indent=2, default=str))

    print("\n" + "="*80)
    print("COST BREAKDOWN")
    print("="*80)
    print(json.dumps(orchestrator.get_cost_breakdown(), indent=2))


if __name__ == "__main__":
    asyncio.run(test_orchestrator())
