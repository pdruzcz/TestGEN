/**
 * Calculator — klasa z podstawowymi operacjami matematycznymi.
 * Golden data sample dla generatora Mocha/Jest.
 */

class Calculator {
  add(a, b) {
    return a + b;
  }

  subtract(a, b) {
    return a - b;
  }

  multiply(a, b) {
    return a * b;
  }

  divide(a, b) {
    if (b === 0) {
      throw new Error('Division by zero');
    }
    return a / b;
  }

  isPositive(n) {
    return n > 0;
  }
}

module.exports = Calculator;
