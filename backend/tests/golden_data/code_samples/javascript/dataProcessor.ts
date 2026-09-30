/**
 * DataProcessor — przetwarzanie danych z walidacja.
 * Golden data sample (TypeScript) dla generatora Mocha/Jest.
 */

interface ProcessResult {
  success: boolean;
  data: Record<string, unknown>[];
  errors: string[];
}

class DataProcessor {
  private processedCount: number = 0;

  process(items: Record<string, unknown>[]): ProcessResult {
    const result: ProcessResult = {
      success: true,
      data: [],
      errors: [],
    };

    if (!items || items.length === 0) {
      result.success = false;
      result.errors.push('No items to process');
      return result;
    }

    for (const item of items) {
      try {
        const validated = this.validate(item);
        result.data.push(validated);
        this.processedCount++;
      } catch (error) {
        result.errors.push(String(error));
        result.success = false;
      }
    }

    return result;
  }

  validate(item: Record<string, unknown>): Record<string, unknown> {
    if (!item || typeof item !== 'object') {
      throw new Error('Invalid item');
    }
    return { ...item, processed: true };
  }

  getProcessedCount(): number {
    return this.processedCount;
  }

  reset(): void {
    this.processedCount = 0;
  }
}

export default DataProcessor;
