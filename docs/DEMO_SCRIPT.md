# Walkthrough (about 10 minutes)

Start with `python start.py` (Windows: double-click `start.bat`) and open `http://127.0.0.1:8000`. The portal opens on the **sign-in page**; nothing else is visible until you sign in. Test accounts are listed under **Test accounts for this installation** (collapsed, bottom-left of the sign-in page). Click a row to sign in. The password for every test account is `Demo@1234`.

1. **Sign-in page (30 s).** Show the accessibility strip (A- / A / A+, Theme, language), the portal selector (Karnataka - Bengaluru / Tamil Nadu - Greater Chennai), the citizen tab (mobile OTP or user ID) and the department tab.
2. **Citizen (2 min).** Sign in as `ka.citizen1` (Lakshmi Narayan). The dashboard shows her complaints, status chart and assigned officers. **File a complaint** → press **Speak** (Chrome/Edge), pick *Speak in*, or type `Water pipeline burst near the temple, water wasting, Jayanagar` → drop a pin on the map → Continue → *Routing details*: BWSSB, High → Submit. The confirmation says **"This complaint has been assigned to Smt. Kavya Shetty, Assistant Executive Engineer (Water Supply), BWSSB - Water Supply & Sewerage"**; press **Read aloud**.
3. **Unclear complaint (30 s).** File `asdkj qwe zzkx` → it goes to the nodal officer for manual routing; no department is guessed.
4. **Officer (2 min).** Account menu → **Add another account** → `ka.officer.water` (Smt. Kavya Shetty). The bell shows the new assignment. Dashboard: assigned to me, awaiting acceptance, SLA breached, due in 24 h, charts by ward and priority, most urgent list. **Work queue** → open the ticket (phone masked; reveal is audited) → Accept → Start → draft a letter → Mark resolved. **Live map**: complaint pins coloured by priority; **Set on map** to share a field position.
5. **Back to the citizen (30 s).** Switch account → the bell shows *Accepted* / *Work started*; the ticket page shows progress, the map and the assigned officer.
6. **Nodal (1 min).** `ka.nodal` (Smt. Kavitha Rao): breached and emergency complaints across departments; **Nodal desk** → route the unclear complaint; it is then auto-assigned to that department's officer.
7. **Helpline (1 min).** `ka.agent1`: queue, **Start practice call** (telephony is not connected) → AI assist → register the complaint for the caller.
8. **Commissioner, audit, content, admin (2 min).** `ka.hod`: city-wide aggregates and department performance table (no personal data). `ka.auditor`: audit events, routing accuracy on the test set, reopened complaints. `ka.content`: articles and schemes awaiting verification. `ka.admin`: users, services up/down, integrations.
9. **Themes and mobile (30 s).** Theme → Dark (maps switch to the dark basemap). Resize to phone width.

All complaint data is synthetic test data (about 95 located complaints per city, inside ward boundaries, 22 categories, spread over 60 days).
