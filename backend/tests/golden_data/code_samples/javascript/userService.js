/**
 * UserService — serwis zarzadzania uzytkownikami.
 * Golden data sample dla generatora Mocha/Jest.
 */

class UserService {
  constructor(userRepository, emailService) {
    this.userRepository = userRepository;
    this.emailService = emailService;
  }

  async getUser(id) {
    if (!id) {
      throw new Error('User ID is required');
    }
    const user = await this.userRepository.findById(id);
    if (!user) {
      return null;
    }
    return user;
  }

  async createUser(userData) {
    if (!userData.email || !userData.name) {
      throw new Error('Email and name are required');
    }
    const existingUser = await this.userRepository.findByEmail(userData.email);
    if (existingUser) {
      throw new Error('User already exists');
    }
    const user = await this.userRepository.create(userData);
    await this.emailService.sendWelcomeEmail(user.email);
    return user;
  }

  async deleteUser(id) {
    const user = await this.userRepository.findById(id);
    if (!user) {
      return false;
    }
    await this.userRepository.delete(id);
    return true;
  }
}

module.exports = UserService;
