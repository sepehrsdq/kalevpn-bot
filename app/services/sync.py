from app.database import get_db
from app.services.xui import XUIManager


def sync_services_with_panel(user_id=None):
    xui = XUIManager()
    ok, msg, clients_map = xui.get_all_panel_clients_map()

    if not ok:
        print("SYNC PANEL ERROR:", msg)
        return False, msg

    if not clients_map:
        print("SYNC WARNING: panel clients map is empty, skipping delete sync")
        return False, "PANEL_CLIENTS_EMPTY_SKIP"

    conn = get_db()

    query = """
        SELECT invoice_id, user_id, client_email, sub_id, status
        FROM invoices
        WHERE client_email IS NOT NULL
    """
    params = ()

    if user_id:
        query += " AND user_id=?"
        params = (user_id,)

    rows = conn.execute(query, params).fetchall()

    deleted_count = 0
    restored_count = 0

    for row in rows:
        invoice_id = row["invoice_id"]
        client_email = row["client_email"]
        sub_id = row["sub_id"]
        current_status = row["status"]

        exists_by_email = bool(client_email and f"email:{client_email}" in clients_map)
        exists_by_sub = bool(sub_id and f"sub:{sub_id}" in clients_map)

        exists_in_panel = exists_by_email or exists_by_sub

        if exists_in_panel:
            if current_status == "PANEL_DELETED":
                conn.execute(
                    """
                    UPDATE invoices
                    SET status='DELIVERED',
                        usage_disabled=0
                    WHERE invoice_id=?
                    """,
                    (invoice_id,),
                )
                restored_count += 1
        else:
            if current_status != "PANEL_DELETED":
                conn.execute(
                    """
                    UPDATE invoices
                    SET status='PANEL_DELETED',
                        usage_disabled=1
                    WHERE invoice_id=?
                    """,
                    (invoice_id,),
                )
                deleted_count += 1

    conn.commit()
    conn.close()

    return True, f"SYNC_OK deleted={deleted_count} restored={restored_count}"