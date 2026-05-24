// f010 c004 — thin accessors over window.boot. Read-only.

const boot = (typeof window !== 'undefined' && window.boot) || {};

export function useSession() {
  return {
    user: boot.session_user,
    fullName: boot.session_user_full_name || boot.session_user,
    image: boot.session_user_image || null,
    csrfToken: boot.csrf_token,
  };
}

export function useSysDefaults() {
  return boot.sysdefaults || {};
}

export function useCashewSettings() {
  return boot.cashew_settings || {};
}

export function useDefaultPeriod() {
  return {
    start: boot.default_period_start || null,
    end: boot.default_period_end || null,
  };
}

export function hasWriteSettings() {
  return Boolean(boot.can_write_settings);
}

export function useRealtimeToken() {
  return boot.realtime_token || null;
}

export function useAppVersion() {
  return boot.app_version || null;
}

export function rawBoot() {
  return boot;
}
