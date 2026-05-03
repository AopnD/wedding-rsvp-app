from __future__ import annotations

import html
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.core.database import SessionLocal, create_database
from app.services.rsvp_service import (
    GuestInviteNotFoundError,
    InvalidAttendingCountError,
    InvalidRsvpResponseError,
    get_guest_by_invite_code,
    submit_rsvp_response,
)


logger = logging.getLogger(__name__)

app = FastAPI(title="Local Wedding RSVP Server")


@app.on_event("startup")
def on_startup() -> None:
    create_database()
    logger.info("RSVP server started.")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/rsvp/{invite_code}", response_class=HTMLResponse)
def show_rsvp_form(invite_code: str) -> HTMLResponse:
    db = SessionLocal()

    try:
        guest = get_guest_by_invite_code(db=db, invite_code=invite_code)
        event = guest.event

        couple_names = html.escape(event.couple_names)
        guest_name = html.escape(guest.full_name)
        wedding_date = html.escape(event.wedding_date or "the wedding")
        venue_name = html.escape(event.venue_name or "")
        invite_code_escaped = html.escape(invite_code)

        venue_html = ""
        if venue_name:
            venue_html = f"<p><strong>Venue:</strong> {venue_name}</p>"

        html_content = f"""
        <!doctype html>
        <html lang="en">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Wedding RSVP</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        max-width: 720px;
                        margin: 40px auto;
                        padding: 0 20px;
                        line-height: 1.5;
                        background: #f7f7f7;
                    }}
                    .card {{
                        background: white;
                        border: 1px solid #ddd;
                        border-radius: 12px;
                        padding: 24px;
                    }}
                    label {{
                        display: block;
                        margin-top: 16px;
                        font-weight: bold;
                    }}
                    input, select, textarea, button {{
                        width: 100%;
                        padding: 10px;
                        margin-top: 6px;
                        font-size: 16px;
                        box-sizing: border-box;
                    }}
                    button {{
                        margin-top: 20px;
                        cursor: pointer;
                    }}
                    .muted {{
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Wedding RSVP</h1>
                    <p>Hello {guest_name},</p>
                    <p>You are invited to the wedding of <strong>{couple_names}</strong>.</p>
                    <p><strong>Date:</strong> {wedding_date}</p>
                    {venue_html}

                    <p class="muted">
                        You can RSVP for up to {guest.invited_count} guest(s).
                    </p>

                    <form method="post" action="/rsvp/{invite_code_escaped}">
                        <label for="response">Will you attend?</label>
                        <select id="response" name="response" required>
                            <option value="yes">Yes, I/we will attend</option>
                            <option value="no">No, I/we cannot attend</option>
                        </select>

                        <label for="attending_count">How many people will attend?</label>
                        <input
                            id="attending_count"
                            name="attending_count"
                            type="number"
                            min="0"
                            max="{guest.invited_count}"
                            value="{guest.invited_count}"
                            required
                        >

                        <label for="notes">Notes / dietary requests</label>
                        <textarea id="notes" name="notes" rows="4"></textarea>

                        <button type="submit">Submit RSVP</button>
                    </form>
                </div>
            </body>
        </html>
        """

        return HTMLResponse(content=html_content)

    except GuestInviteNotFoundError:
        return HTMLResponse(
            content=_simple_page(
                title="RSVP link not found",
                message="This RSVP link was not found. Please check the link and try again.",
            ),
            status_code=404,
        )

    except Exception:
        logger.exception("Failed to show RSVP form.")
        return HTMLResponse(
            content=_simple_page(
                title="Something went wrong",
                message="Could not load this RSVP page.",
            ),
            status_code=500,
        )

    finally:
        db.close()


@app.post("/rsvp/{invite_code}", response_class=HTMLResponse)
async def submit_rsvp_form(invite_code: str, request: Request) -> HTMLResponse:
    form_data = await request.form()

    response = str(form_data.get("response", ""))
    notes = str(form_data.get("notes", ""))

    try:
        attending_count = int(str(form_data.get("attending_count", "0")))
    except ValueError:
        attending_count = -1

    db = SessionLocal()

    try:
        result = submit_rsvp_response(
            db=db,
            invite_code=invite_code,
            response=response,
            attending_count=attending_count,
            notes=notes,
        )

        message = (
            f"Thank you, {html.escape(result.guest_name)}. "
            f"Your RSVP was saved successfully."
        )

        return HTMLResponse(
            content=_simple_page(
                title="RSVP saved",
                message=message,
            )
        )

    except GuestInviteNotFoundError:
        return HTMLResponse(
            content=_simple_page(
                title="RSVP link not found",
                message="This RSVP link was not found. Please check the link and try again.",
            ),
            status_code=404,
        )

    except (InvalidRsvpResponseError, InvalidAttendingCountError) as exc:
        return HTMLResponse(
            content=_simple_page(
                title="Invalid RSVP",
                message=str(exc),
            ),
            status_code=400,
        )

    except Exception:
        logger.exception("Failed to submit RSVP.")
        return HTMLResponse(
            content=_simple_page(
                title="Something went wrong",
                message="Could not save this RSVP response.",
            ),
            status_code=500,
        )

    finally:
        db.close()


def _simple_page(title: str, message: str) -> str:
    safe_title = html.escape(title)
    safe_message = html.escape(message)

    return f"""
    <!doctype html>
    <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>{safe_title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 720px;
                    margin: 40px auto;
                    padding: 0 20px;
                    line-height: 1.5;
                    background: #f7f7f7;
                }}
                .card {{
                    background: white;
                    border: 1px solid #ddd;
                    border-radius: 12px;
                    padding: 24px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>{safe_title}</h1>
                <p>{safe_message}</p>
            </div>
        </body>
    </html>
    """