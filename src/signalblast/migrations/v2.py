"""v2: drops the timestamps that were never needed, so they are not kept about anyone."""

SQL = """
ALTER TABLE subscribers DROP COLUMN subscribed_at;
ALTER TABLE banned_users DROP COLUMN banned_at;
ALTER TABLE admins DROP COLUMN added_at;
"""
