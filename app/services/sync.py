from app.database import get_db
from app.services.xui import XUIManager


def sync_services_with_panel(user_id=None):
    xui = XUIManager()
    ok, msg, clients_map = xui.get_panel_clients_map()

    if not ok:
        print("SYNC PANEL ERROR:", msg)
        return False, msg

    conn = get_db()

    query = """
        SELECT invoice_id, client_email
        FROM invoices
        WHERE client_email IS NOT NULL
        AND status != 'PANEL_DELETED'
    """
    params = ()

    if user_id:
        query += " AND user_id=?"
        params = (user_id,)

    rows = conn.execute(query, params).fetchall()

    deleted_count = 0

    for row in rows:
        invoice_id = row["invoice_id"]
        client_email = row["client_email"]

        if client_email not in clients_map:
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

    return True, f"SYNC_OK deleted={deleted_count}"
