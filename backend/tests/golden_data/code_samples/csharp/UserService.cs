namespace MyApp.Services;

using System.Collections.Generic;
using MyApp.Data;

/// <summary>Service zarzadzajacy uzytkownikami.</summary>
public class UserService
{
    private readonly IUserRepository _repository;

    public UserService(IUserRepository repository)
    {
        _repository = repository;
    }

    public User? GetUser(int id)
    {
        return _repository.FindById(id);
    }

    public User CreateUser(string name, string email)
    {
        if (string.IsNullOrEmpty(name)) throw new ArgumentException("Name is required");
        if (string.IsNullOrEmpty(email)) throw new ArgumentException("Email is required");

        var user = new User { Name = name, Email = email };
        _repository.Save(user);
        return user;
    }

    public bool DeleteUser(int id)
    {
        var user = _repository.FindById(id);
        if (user == null) return false;
        _repository.Delete(user);
        return true;
    }
}

public class User
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Email { get; set; } = "";
}
