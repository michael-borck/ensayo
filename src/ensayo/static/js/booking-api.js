/**
 * Ensayo Booking API Client — wraps the sim-booking-api endpoints.
 * Reads the API URL from the booking gate element's data-booking-api attribute.
 */

const BookingAPI = {
    _baseUrl: null,

    getBaseUrl() {
        if (this._baseUrl) return this._baseUrl;
        const gate = document.querySelector('[data-booking-api]');
        this._baseUrl = gate ? gate.dataset.bookingApi : '';
        return this._baseUrl;
    },

    async getEmployeeSlots(employeeId) {
        const url = `${this.getBaseUrl()}/employees/${employeeId}/slots`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch slots');
        return res.json();
    },

    async createAppointment(data) {
        const res = await fetch(`${this.getBaseUrl()}/appointments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error('Failed to create appointment');
        return res.json();
    },

    async checkAccess(studentEmail, employeeId) {
        const res = await fetch(`${this.getBaseUrl()}/access/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: studentEmail, employee_id: employeeId }),
        });
        if (!res.ok) return { has_access: false };
        return res.json();
    },
};
