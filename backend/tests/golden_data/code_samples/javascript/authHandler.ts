/**
 * AuthHandler — obsluga autoryzacji i tokenow JWT.
 * Golden data sample (TypeScript) dla generatora Mocha/Jest.
 */

interface TokenPayload {
  userId: string;
  role: string;
  exp: number;
}

class AuthHandler {
  private secret: string;
  private tokenExpiry: number;

  constructor(secret: string, tokenExpiry: number = 3600) {
    this.secret = secret;
    this.tokenExpiry = tokenExpiry;
  }

  generateToken(userId: string, role: string): string {
    if (!userId) {
      throw new Error('User ID is required');
    }
    const payload: TokenPayload = {
      userId,
      role,
      exp: Date.now() + this.tokenExpiry * 1000,
    };
    return btoa(JSON.stringify(payload));
  }

  validateToken(token: string): TokenPayload | null {
    if (!token) {
      return null;
    }
    try {
      const payload: TokenPayload = JSON.parse(atob(token));
      if (payload.exp < Date.now()) {
        return null;
      }
      return payload;
    } catch {
      return null;
    }
  }

  isAuthorized(token: string, requiredRole: string): boolean {
    const payload = this.validateToken(token);
    if (!payload) {
      return false;
    }
    return payload.role === requiredRole || payload.role === 'admin';
  }
}

export default AuthHandler;
