// f010 c004 — D5.c shell-level HTTP error interceptors → frappe-ui Toast.

import { toast, frappeRequest } from 'frappe-ui';

function toastFor(status, detail) {
  if (status === 401) {
    toast.warning('Please sign in again.', { title: 'Session expired' });
    return;
  }
  if (status === 403) {
    toast.error(detail || "You don't have permission for that action.", { title: 'Not allowed' });
    return;
  }
  if (status >= 500) {
    toast.error(detail || 'Something went wrong on the server.', { title: 'Server error' });
    return;
  }
  if (!status) {
    toast.error('Could not reach the server. Check your connection.', { title: 'Network error' });
  }
}

function extractDetail(error) {
  const data = error?.response?.data || error?.data || {};
  const messages = data._server_messages;
  if (typeof messages === 'string') {
    try {
      const parsed = JSON.parse(messages);
      const first = Array.isArray(parsed) ? parsed[0] : parsed;
      if (typeof first === 'string') {
        try { return JSON.parse(first).message || first; } catch (_) { return first; }
      }
      return first?.message;
    } catch (_) {
      return messages;
    }
  }
  return data.message || data.exc_type || error?.message;
}

export function installErrorInterceptors() {
  const axiosInstance = frappeRequest && frappeRequest.axios;
  if (axiosInstance?.interceptors?.response) {
    axiosInstance.interceptors.response.use(
      (resp) => resp,
      (error) => {
        const status = error?.response?.status;
        toastFor(status, extractDetail(error));
        return Promise.reject(error);
      },
    );
    return;
  }
  if (typeof window !== 'undefined' && typeof window.fetch === 'function') {
    const origFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      try {
        const resp = await origFetch(input, init);
        if (!resp.ok) toastFor(resp.status);
        return resp;
      } catch (err) {
        toastFor(undefined);
        throw err;
      }
    };
  }
}
