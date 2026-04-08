/**
 * Ensayo Booking Gate — controls chatbot access via the booking system.
 * If the booking API is unavailable, falls back to direct access.
 */

document.addEventListener('DOMContentLoaded', function () {
    const gate = document.getElementById('booking-gate');
    if (!gate) return;

    const chatContainer = document.getElementById('chatbot-container');
    const employeeId = gate.dataset.employeeId;
    const apiUrl = gate.dataset.bookingApi;

    if (!apiUrl) {
        // No booking API configured — direct access
        showChat();
        return;
    }

    // Check if API is reachable
    fetch(apiUrl + '/employees')
        .then(r => { if (!r.ok) throw new Error(); return r.json(); })
        .then(() => setupGate())
        .catch(() => {
            // API unreachable — fallback to direct access
            showChat();
        });

    function setupGate() {
        if (chatContainer) chatContainer.style.display = 'none';
        gate.style.display = 'block';

        const scheduleBtn = document.getElementById('booking-schedule-btn');
        const attendBtn = document.getElementById('booking-attend-btn');

        if (scheduleBtn) {
            scheduleBtn.addEventListener('click', () => showBookingModal());
        }
        if (attendBtn) {
            attendBtn.addEventListener('click', () => checkExistingBooking());
        }
    }

    function showChat() {
        if (gate) gate.style.display = 'none';
        if (chatContainer) chatContainer.style.display = 'block';
    }

    function showBookingModal() {
        // Simplified booking flow — in production, this would show a full modal
        const email = prompt('Enter your email to book an appointment:');
        if (!email) return;

        const name = prompt('Enter your name:');
        if (!name) return;

        BookingAPI.getEmployeeSlots(employeeId)
            .then(slots => {
                if (!slots.length) {
                    alert('No slots available. Try again later.');
                    return;
                }
                // Auto-book the first available slot for simplicity
                return BookingAPI.createAppointment({
                    student_email: email,
                    student_name: name,
                    employee_id: employeeId,
                    scheduled_start: slots[0].start,
                    scheduled_end: slots[0].end,
                });
            })
            .then(appt => {
                if (appt) {
                    alert('Appointment booked! You can now chat.');
                    showChat();
                }
            })
            .catch(() => {
                alert('Booking failed. Granting direct access.');
                showChat();
            });
    }

    function checkExistingBooking() {
        const email = prompt('Enter the email you booked with:');
        if (!email) return;

        BookingAPI.checkAccess(email, employeeId)
            .then(result => {
                if (result.has_access) {
                    showChat();
                } else {
                    alert('No active appointment found. Please schedule one first.');
                }
            })
            .catch(() => {
                alert('Could not verify. Granting direct access.');
                showChat();
            });
    }
});
