"""initial schema — 기획서 10장 전체 스키마

Revision ID: 0001
Revises:
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

vote_choice = sa.Enum("찬성", "반대", "기권", "불참", name="votechoice")
answer_choice = sa.Enum("찬성", "반대", "모름", name="answerchoice")
question_status = sa.Enum("초안", "검토중", "승인", "아카이브", name="questionstatus")
question_creator = sa.Enum("auto", "admin", name="questioncreator")
pal_status = sa.Enum("진행중", "종료", name="palstatus")


def upgrade() -> None:
    op.create_table(
        "party",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("color_hex", sa.String(7), nullable=True),
    )

    op.create_table(
        "person",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("party.id"), nullable=True),
        sa.Column("district", sa.String(120), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("attendance_rate", sa.Float(), nullable=True),
        sa.Column("profile_source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_person_name", "person", ["name"])

    op.create_table(
        "district",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("region", sa.String(60), nullable=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "bill",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_no", sa.String(40), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("proposer_id", sa.Integer(), sa.ForeignKey("person.id"), nullable=True),
        sa.Column("proposed_date", sa.Date(), nullable=True),
        sa.Column("committee", sa.String(120), nullable=True),
        sa.Column("status", sa.String(60), nullable=True),
        sa.Column("law_link", sa.Text(), nullable=True),
        sa.Column("likms_url", sa.Text(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pal_status", pal_status, nullable=True),
        sa.Column("pal_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_bill_bill_no", "bill", ["bill_no"])

    op.create_table(
        "vote",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bill.id"), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vote_bill_id", "vote", ["bill_id"])

    op.create_table(
        "vote_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vote_id", sa.Integer(), sa.ForeignKey("vote.id"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), nullable=False),
        sa.Column("choice", vote_choice, nullable=False),
        sa.UniqueConstraint("vote_id", "person_id", name="uq_vote_person"),
    )
    op.create_index("ix_vote_record_vote_id", "vote_record", ["vote_id"])
    op.create_index("ix_vote_record_person_id", "vote_record", ["person_id"])

    op.create_table(
        "criminal_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person.id"), nullable=False),
        sa.Column("charge", sa.Text(), nullable=False),
        sa.Column("sentence", sa.Text(), nullable=True),
        sa.Column("date_sentenced", sa.Date(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_criminal_record_person_id", "criminal_record", ["person_id"])

    op.create_table(
        "issue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False, unique=True),
    )

    op.create_table(
        "question",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issue.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("agree_meaning", sa.Text(), nullable=False),
        sa.Column("disagree_meaning", sa.Text(), nullable=False),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("bill.id"), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("status", question_status, nullable=False, server_default="초안"),
        sa.Column("created_by", question_creator, nullable=False, server_default="admin"),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_question_issue_id", "question", ["issue_id"])
    op.create_index("ix_question_bill_id", "question", ["bill_id"])
    op.create_index("ix_question_status", "question", ["status"])

    op.create_table(
        "answer",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False),
        sa.Column("choice", answer_choice, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_answer_session_id", "answer", ["session_id"])
    op.create_index("ix_answer_question_id", "answer", ["question_id"])

    op.create_table(
        "relationship",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("from_node", sa.String(120), nullable=False),
        sa.Column("from_type", sa.String(40), nullable=False),
        sa.Column("to_node", sa.String(120), nullable=False),
        sa.Column("to_type", sa.String(40), nullable=False),
        sa.Column("relation_type", sa.String(80), nullable=False),
        sa.Column("evidence_url", sa.Text(), nullable=False),  # 🟡 NOT NULL
        sa.Column("curated_by", sa.String(100), nullable=True),
        sa.Column("curated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("relationship")
    op.drop_table("answer")
    op.drop_table("question")
    op.drop_table("issue")
    op.drop_table("criminal_record")
    op.drop_table("vote_record")
    op.drop_table("vote")
    op.drop_table("bill")
    op.drop_table("district")
    op.drop_table("person")
    op.drop_table("party")
    for enum in (pal_status, question_creator, question_status, answer_choice, vote_choice):
        enum.drop(op.get_bind(), checkfirst=True)
