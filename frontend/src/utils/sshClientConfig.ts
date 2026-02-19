export type SshAuthMethod = 'password' | 'key';

export type SshClientConfig = {
  host: string;
  port: string;
  username: string;
  authMethod: SshAuthMethod;
  password: string;
  hostFingerprint: string;
};

export type SshConnectPayload = {
  host: string;
  port: number;
  username: string;
  authMethod: SshAuthMethod;
  password?: string;
  hostFingerprint?: string;
};

const SSH_CLIENT_CONFIG_KEY = 'lyra.ssh_client_config.v1';

const DEFAULT_SSH_CONFIG: SshClientConfig = {
  host: '',
  port: '22',
  username: '',
  authMethod: 'password',
  password: '',
  hostFingerprint: '',
};

const sanitizePort = (value: unknown): string => {
  const raw = String(value ?? '').trim();
  if (!raw) return '22';
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0 || parsed > 65535) return '22';
  return String(parsed);
};

const sanitizeAuthMethod = (value: unknown): SshAuthMethod => {
  return String(value ?? '').toLowerCase() === 'key' ? 'key' : 'password';
};

const normalizeHost = (value: unknown): string => String(value ?? '').trim();
const normalizeUsername = (value: unknown): string => String(value ?? '').trim();
const normalizeOptional = (value: unknown): string => String(value ?? '').trim();

export const readStoredSshClientConfig = (): SshClientConfig => {
  if (typeof window === 'undefined') return { ...DEFAULT_SSH_CONFIG };
  try {
    const raw = window.localStorage.getItem(SSH_CLIENT_CONFIG_KEY);
    if (!raw) return { ...DEFAULT_SSH_CONFIG };
    const parsed = JSON.parse(raw) as Partial<SshClientConfig> | null;
    return {
      host: normalizeHost(parsed?.host),
      port: sanitizePort(parsed?.port),
      username: normalizeUsername(parsed?.username),
      authMethod: sanitizeAuthMethod(parsed?.authMethod),
      password: normalizeOptional(parsed?.password),
      hostFingerprint: normalizeOptional(parsed?.hostFingerprint),
    };
  } catch {
    return { ...DEFAULT_SSH_CONFIG };
  }
};

export const writeStoredSshClientConfig = (input: Partial<SshClientConfig>): SshClientConfig => {
  const next: SshClientConfig = {
    host: normalizeHost(input.host),
    port: sanitizePort(input.port),
    username: normalizeUsername(input.username),
    authMethod: sanitizeAuthMethod(input.authMethod),
    password: normalizeOptional(input.password),
    hostFingerprint: normalizeOptional(input.hostFingerprint),
  };
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(SSH_CLIENT_CONFIG_KEY, JSON.stringify(next));
  }
  return next;
};

export const clearStoredSshClientConfig = (): void => {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(SSH_CLIENT_CONFIG_KEY);
};

export const isSshClientConfigReady = (
  config: SshClientConfig,
  opts?: { requireAuth?: boolean },
): boolean => {
  if (!config.host || !config.username || !config.authMethod) return false;
  if (opts?.requireAuth === false) return true;
  if (config.authMethod === 'password') return Boolean(config.password);
  return true;
};

export const toSshConnectPayload = (config: SshClientConfig): SshConnectPayload => {
  const payload: SshConnectPayload = {
    host: config.host,
    port: Number(config.port) || 22,
    username: config.username,
    authMethod: config.authMethod,
  };
  if (config.authMethod === 'password' && config.password) {
    payload.password = config.password;
  }
  if (config.hostFingerprint) {
    payload.hostFingerprint = config.hostFingerprint;
  }
  return payload;
};
