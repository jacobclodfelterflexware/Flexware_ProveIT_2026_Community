"""Neo4j storage for simulated machines."""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from neo4j import AsyncGraphDatabase, AsyncDriver

from ..config import config
from ..models import MachineDefinition, MachineStatus, FieldDefinition, TopicDefinition

logger = logging.getLogger(__name__)


class MachineStore:
    """CRUD operations for SimulatedMachine nodes in Neo4j."""

    def __init__(self):
        self._driver: Optional[AsyncDriver] = None

    async def connect(self) -> None:
        """Connect to Neo4j."""
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        logger.info(f"Connected to Neo4j at {config.neo4j_uri}")
        await self._ensure_constraints()

    async def _ensure_constraints(self) -> None:
        """Ensure Neo4j constraints and indexes exist."""
        async with self._driver.session() as session:
            try:
                await session.run(
                    "CREATE CONSTRAINT sim_machine_name_unique IF NOT EXISTS "
                    "FOR (m:SimulatedMachine) REQUIRE m.name IS UNIQUE"
                )
                logger.info("Ensured unique constraint on SimulatedMachine.name")
            except Exception as e:
                logger.warning(f"Could not create uniqueness constraint: {e}")

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self._driver:
            await self._driver.close()
            logger.info("Disconnected from Neo4j")

    async def create(self, machine: MachineDefinition) -> MachineDefinition:
        """Create a new simulated machine."""
        machine.id = str(uuid4())
        machine.created_at = datetime.utcnow()
        machine.status = MachineStatus.DRAFT

        # Serialize topics for multi-topic machines
        topics_json = json.dumps([
            {"topic_path": t.topic_path, "fields": [f.model_dump() for f in t.fields]}
            for t in machine.topics
        ]) if machine.topics else "[]"

        # Serialize similarity results
        similarity_json = json.dumps(machine.similarity_results) if machine.similarity_results else "[]"

        # Serialize SparkMES structure
        sparkmes_json = None
        if machine.sparkmes:
            sparkmes_json = json.dumps(machine.sparkmes)

        # Serialize SM Profile structure
        smprofile_json = None
        if machine.smprofile:
            smprofile_json = json.dumps(machine.smprofile)

        async with self._driver.session() as session:
            query = """
            CREATE (m:SimulatedMachine {
                id: $id,
                name: $name,
                description: $description,
                machineType: $machine_type,
                topicPath: $topic_path,
                schemaProposalId: $schema_proposal_id,
                fieldDefinitions: $field_definitions,
                topics: $topics,
                publishIntervalMs: $publish_interval_ms,
                imageBase64: $image_base64,
                status: $status,
                createdAt: datetime($created_at),
                createdBy: $created_by,
                similarityResults: $similarity_results,
                sparkmesEnabled: $sparkmes_enabled,
                sparkmes: $sparkmes,
                smprofile: $smprofile
            })
            RETURN m
            """
            await session.run(
                query,
                id=machine.id,
                name=machine.name,
                description=machine.description,
                machine_type=machine.machine_type,
                topic_path=machine.topic_path,
                schema_proposal_id=machine.schema_proposal_id,
                field_definitions=json.dumps([f.model_dump() for f in machine.fields]),
                topics=topics_json,
                publish_interval_ms=machine.publish_interval_ms,
                image_base64=machine.image_base64,
                status=machine.status.value,
                created_at=machine.created_at.isoformat(),
                created_by=machine.created_by or "system",
                similarity_results=similarity_json,
                sparkmes_enabled=machine.sparkmes_enabled,
                sparkmes=sparkmes_json,
                smprofile=smprofile_json
            )

        logger.info(f"Created machine {machine.id}: {machine.name}")
        return machine

    async def get(self, machine_id: str) -> Optional[MachineDefinition]:
        """Get a machine by ID."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})
                RETURN m
                """,
                id=machine_id
            )
            record = await result.single()

            if not record:
                return None

            return self._record_to_machine(record["m"])

    async def get_by_creator(self, creator_name: str) -> Optional[MachineDefinition]:
        """Get the most recent machine created by a specific person."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {createdBy: $name})
                RETURN m
                ORDER BY m.createdAt DESC
                LIMIT 1
                """,
                name=creator_name
            )
            record = await result.single()

            if not record:
                return None

            return self._record_to_machine(record["m"])

    async def list_all(self, status: Optional[MachineStatus] = None) -> list[MachineDefinition]:
        """List all machines, optionally filtered by status."""
        async with self._driver.session() as session:
            if status:
                query = """
                MATCH (m:SimulatedMachine {status: $status})
                RETURN m
                ORDER BY m.createdAt DESC
                """
                result = await session.run(query, status=status.value)
            else:
                query = """
                MATCH (m:SimulatedMachine)
                RETURN m
                ORDER BY m.createdAt DESC
                """
                result = await session.run(query)

            machines = []
            async for record in result:
                machines.append(self._record_to_machine(record["m"]))

            return machines

    async def update(self, machine: MachineDefinition) -> MachineDefinition:
        """Update a machine."""
        # Serialize topics for multi-topic machines
        topics_json = json.dumps([
            {"topic_path": t.topic_path, "fields": [f.model_dump() for f in t.fields]}
            for t in machine.topics
        ]) if machine.topics else "[]"

        # Serialize SparkMES structure
        sparkmes_json = None
        if machine.sparkmes:
            sparkmes_json = json.dumps(machine.sparkmes)

        # Serialize SM Profile structure
        smprofile_json = None
        if machine.smprofile:
            smprofile_json = json.dumps(machine.smprofile)

        async with self._driver.session() as session:
            query = """
            MATCH (m:SimulatedMachine {id: $id})
            SET m.name = $name,
                m.description = $description,
                m.machineType = $machine_type,
                m.topicPath = $topic_path,
                m.schemaProposalId = $schema_proposal_id,
                m.fieldDefinitions = $field_definitions,
                m.topics = $topics,
                m.publishIntervalMs = $publish_interval_ms,
                m.status = $status,
                m.approvedAt = CASE WHEN $approved_at IS NOT NULL THEN datetime($approved_at) ELSE m.approvedAt END,
                m.lastPublishedAt = CASE WHEN $last_published_at IS NOT NULL THEN datetime($last_published_at) ELSE m.lastPublishedAt END,
                m.sparkmesEnabled = $sparkmes_enabled,
                m.sparkmes = $sparkmes,
                m.smprofile = $smprofile
            RETURN m
            """
            await session.run(
                query,
                id=machine.id,
                name=machine.name,
                description=machine.description,
                machine_type=machine.machine_type,
                topic_path=machine.topic_path,
                schema_proposal_id=machine.schema_proposal_id,
                field_definitions=json.dumps([f.model_dump() for f in machine.fields]),
                topics=topics_json,
                publish_interval_ms=machine.publish_interval_ms,
                status=machine.status.value,
                approved_at=machine.approved_at.isoformat() if machine.approved_at else None,
                last_published_at=machine.last_published_at.isoformat() if machine.last_published_at else None,
                sparkmes_enabled=machine.sparkmes_enabled,
                sparkmes=sparkmes_json,
                smprofile=smprofile_json
            )

        logger.info(f"Updated machine {machine.id}")
        return machine

    async def update_status(self, machine_id: str, status: MachineStatus) -> bool:
        """Update just the status of a machine."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})
                SET m.status = $status
                RETURN m.id
                """,
                id=machine_id,
                status=status.value
            )
            record = await result.single()
            return record is not None

    async def update_last_published(self, machine_id: str) -> None:
        """Update the lastPublishedAt timestamp."""
        async with self._driver.session() as session:
            await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})
                SET m.lastPublishedAt = datetime()
                """,
                id=machine_id
            )

    async def delete(self, machine_id: str) -> bool:
        """Delete a machine and all related nodes (LadderLogic, Predictions, Regressions, etc.)."""
        async with self._driver.session() as session:
            # Delete related LadderLogic nodes
            await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})-[:HAS_LADDER_LOGIC]->(l:LadderLogic)
                DETACH DELETE l
                """,
                id=machine_id
            )

            # Delete related Prediction nodes
            await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})-[:HAS_PREDICTION]->(p:Prediction)
                DETACH DELETE p
                """,
                id=machine_id
            )

            # Delete related Regression nodes
            await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})-[:HAS_REGRESSION]->(r:Regression)
                DETACH DELETE r
                """,
                id=machine_id
            )

            # Delete the machine and any remaining relationships
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {id: $id})
                DETACH DELETE m
                RETURN count(*) as deleted
                """,
                id=machine_id
            )
            record = await result.single()
            deleted = record["deleted"] if record else 0

        if deleted > 0:
            logger.info(f"Deleted machine {machine_id} and all related nodes")
            return True
        return False

    async def get_machine_summary(self) -> list[dict]:
        """
        Get summary of all existing machines (names and types).
        Used to prevent AI from generating duplicate machines.
        """
        async with self._driver.session() as session:
            result = await session.run("""
                MATCH (m:SimulatedMachine)
                RETURN m.name as name, m.machineType as machine_type
                ORDER BY m.createdAt DESC
            """)

            machines = []
            async for record in result:
                machines.append({
                    "name": record["name"],
                    "machine_type": record["machine_type"],
                })

            logger.info(f"Retrieved {len(machines)} existing machines for novelty check")
            return machines

    async def find_by_name(self, name: str) -> Optional[dict]:
        """Check if a machine with the given name already exists."""
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {name: $name})
                RETURN m.id as id, m.name as name
                LIMIT 1
                """,
                name=name
            )
            record = await result.single()
            if record:
                return {"id": record["id"], "name": record["name"]}
            return None

    async def get_random_topic_context(self, limit: int = 10) -> list[dict]:
        """
        Query random Topic nodes with their most recent Message payload.

        Used to provide context for AI machine generation - helps the LLM
        understand what kinds of machines already exist in the knowledge graph.

        Returns a list of dicts with:
        - topic_path: str
        - payload: dict (parsed rawPayload)
        - field_names: list[str]
        """
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (t:Topic)
                WHERE EXISTS { (t)-[:HAS_MESSAGE]->(:Message) }
                WITH t, rand() AS r
                ORDER BY r
                LIMIT 50
                MATCH (t)-[:HAS_MESSAGE]->(m:Message)
                WHERE m.rawPayload IS NOT NULL AND m.rawPayload STARTS WITH '{'
                WITH t.path AS topicPath, m.rawPayload AS payload, m.timestamp AS ts
                ORDER BY ts DESC
                WITH topicPath, collect(payload)[0] AS latestPayload
                WHERE latestPayload IS NOT NULL
                RETURN topicPath, latestPayload
                LIMIT $limit
                """,
                limit=limit
            )

            topics = []
            async for record in result:
                try:
                    payload = json.loads(record["latestPayload"])
                    if isinstance(payload, dict):
                        topics.append({
                            "topic_path": record["topicPath"],
                            "payload": payload,
                            "field_names": list(payload.keys()),
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

            logger.info(f"Retrieved {len(topics)} random topics for context")
            return topics

    async def save_ladder_logic(
        self,
        machine_id: str,
        rungs: list[dict],
        io_mapping: dict,
        rationale: Optional[str] = None
    ) -> dict:
        """
        Save ladder logic for a machine.

        Creates a LadderLogic node and links it to the SimulatedMachine via HAS_LADDER_LOGIC relationship.
        If ladder logic already exists for this machine, it will be replaced.

        Args:
            machine_id: The machine ID to associate with
            rungs: The ladder program rungs (list of dicts)
            io_mapping: The IO mapping (inputs, outputs, internal)
            rationale: Optional explanation from the LLM

        Returns:
            Dict with the saved ladder logic data
        """
        rungs_json = json.dumps(rungs)
        io_mapping_json = json.dumps(io_mapping)

        async with self._driver.session() as session:
            # Delete any existing ladder logic for this machine
            await session.run(
                """
                MATCH (m:SimulatedMachine {id: $machine_id})-[r:HAS_LADDER_LOGIC]->(l:LadderLogic)
                DETACH DELETE l
                """,
                machine_id=machine_id
            )

            # Create new ladder logic node and relationship
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {id: $machine_id})
                CREATE (l:LadderLogic {
                    rungs: $rungs,
                    ioMapping: $io_mapping,
                    rationale: $rationale,
                    createdAt: datetime()
                })
                CREATE (m)-[:HAS_LADDER_LOGIC]->(l)
                RETURN l.rungs as rungs, l.ioMapping as io_mapping, l.rationale as rationale, l.createdAt as created_at
                """,
                machine_id=machine_id,
                rungs=rungs_json,
                io_mapping=io_mapping_json,
                rationale=rationale
            )

            record = await result.single()
            if not record:
                raise ValueError(f"Machine {machine_id} not found")

            logger.info(f"Saved ladder logic for machine {machine_id} with {len(rungs)} rungs")

            return {
                "rungs": json.loads(record["rungs"]),
                "io_mapping": json.loads(record["io_mapping"]),
                "rationale": record["rationale"],
                "created_at": record["created_at"].isoformat() if hasattr(record["created_at"], "isoformat") else str(record["created_at"])
            }

    async def get_ladder_logic(self, machine_id: str) -> Optional[dict]:
        """
        Get ladder logic for a machine.

        Args:
            machine_id: The machine ID

        Returns:
            Dict with ladder logic data, or None if not found
        """
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {id: $machine_id})-[:HAS_LADDER_LOGIC]->(l:LadderLogic)
                RETURN l.rungs as rungs, l.ioMapping as io_mapping, l.rationale as rationale, l.createdAt as created_at
                """,
                machine_id=machine_id
            )

            record = await result.single()
            if not record:
                return None

            created_at = record["created_at"]
            if hasattr(created_at, "to_native"):
                created_at = created_at.to_native()

            return {
                "rungs": json.loads(record["rungs"]) if record["rungs"] else [],
                "io_mapping": json.loads(record["io_mapping"]) if record["io_mapping"] else {},
                "rationale": record["rationale"],
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
            }

    async def delete_ladder_logic(self, machine_id: str) -> bool:
        """
        Delete ladder logic for a machine.

        Args:
            machine_id: The machine ID

        Returns:
            True if deleted, False if not found
        """
        async with self._driver.session() as session:
            result = await session.run(
                """
                MATCH (m:SimulatedMachine {id: $machine_id})-[r:HAS_LADDER_LOGIC]->(l:LadderLogic)
                DETACH DELETE l
                RETURN count(*) as deleted
                """,
                machine_id=machine_id
            )

            record = await result.single()
            deleted = record["deleted"] if record else 0

            if deleted > 0:
                logger.info(f"Deleted ladder logic for machine {machine_id}")
                return True
            return False

    def _record_to_machine(self, node: dict) -> MachineDefinition:
        """Convert a Neo4j node to a MachineDefinition."""
        # Parse field definitions from JSON (for single-topic backward compat)
        fields_json = node.get("fieldDefinitions", "[]")
        fields_data = json.loads(fields_json) if fields_json else []
        fields = [FieldDefinition(**f) for f in fields_data]

        # Parse topics from JSON (for multi-topic machines)
        topics_json = node.get("topics", "[]")
        topics_data = json.loads(topics_json) if topics_json else []
        topics = []
        for t in topics_data:
            topic_fields = [FieldDefinition(**f) for f in t.get("fields", [])]
            topics.append(TopicDefinition(topic_path=t["topic_path"], fields=topic_fields))

        # Parse datetime fields
        created_at = None
        if node.get("createdAt"):
            created_at = node["createdAt"].to_native() if hasattr(node["createdAt"], "to_native") else node["createdAt"]

        approved_at = None
        if node.get("approvedAt"):
            approved_at = node["approvedAt"].to_native() if hasattr(node["approvedAt"], "to_native") else node["approvedAt"]

        last_published_at = None
        if node.get("lastPublishedAt"):
            last_published_at = node["lastPublishedAt"].to_native() if hasattr(node["lastPublishedAt"], "to_native") else node["lastPublishedAt"]

        # Parse similarity results from JSON
        similarity_json = node.get("similarityResults", "[]")
        similarity_results = json.loads(similarity_json) if similarity_json else []

        # Parse SparkMES structure from JSON (backward compatible - defaults to enabled)
        sparkmes_enabled = node.get("sparkmesEnabled", True)
        sparkmes = None
        sparkmes_json = node.get("sparkmes") or node.get("sparkmesConfig")  # Fallback for backward compat
        if sparkmes_json:
            try:
                sparkmes = json.loads(sparkmes_json)
            except (json.JSONDecodeError, TypeError):
                sparkmes = None

        # Parse SM Profile structure from JSON
        smprofile = None
        smprofile_json = node.get("smprofile")
        if smprofile_json:
            try:
                smprofile = json.loads(smprofile_json)
            except (json.JSONDecodeError, TypeError):
                smprofile = None

        return MachineDefinition(
            id=node["id"],
            name=node.get("name") or f"machine-{node['id'][:8]}",  # Fallback for legacy records
            description=node.get("description"),
            machine_type=node.get("machineType"),
            topic_path=node.get("topicPath"),  # May be None for multi-topic
            schema_proposal_id=node.get("schemaProposalId"),
            fields=fields,
            topics=topics,
            publish_interval_ms=node.get("publishIntervalMs", 5000),
            image_base64=node.get("imageBase64"),
            status=MachineStatus(node.get("status", "draft")),
            created_at=created_at,
            created_by=node.get("createdBy"),
            approved_at=approved_at,
            last_published_at=last_published_at,
            similarity_results=similarity_results,
            sparkmes_enabled=sparkmes_enabled,
            sparkmes=sparkmes,
            smprofile=smprofile
        )


# Global instance
machine_store = MachineStore()
