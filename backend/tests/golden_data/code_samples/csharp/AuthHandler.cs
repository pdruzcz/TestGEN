namespace MyApp.Security;

using System;

/// <summary>Obsluga autentykacji.</summary>
public class AuthHandler
{
    public bool ValidateCredentials(string username, string password)
    {
        if (string.IsNullOrEmpty(username)) return false;
        if (string.IsNullOrEmpty(password)) return false;
        if (password.Length < 8) return false;
        return true;
    }

    public string HashPassword(string password)
    {
        if (string.IsNullOrEmpty(password)) throw new ArgumentNullException(nameof(password));
        return Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(password));
    }

    public bool VerifyPassword(string password, string hash)
    {
        var computedHash = HashPassword(password);
        return computedHash == hash;
    }
}
