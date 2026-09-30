namespace MyApp.Services;

using System.Collections.Generic;
using System.Linq;

/// <summary>Przetwarza dane wejsciowe.</summary>
public class DataProcessor
{
    public List<int> FilterPositive(List<int> data)
    {
        return data.Where(x => x > 0).ToList();
    }

    public double CalculateAverage(List<int> data)
    {
        if (data == null || data.Count == 0) throw new InvalidOperationException("Data cannot be empty");
        return data.Average();
    }

    public Dictionary<string, int> GroupByLength(List<string> words)
    {
        return words.GroupBy(w => w.Length)
                    .ToDictionary(g => $"length_{g.Key}", g => g.Count());
    }
}
