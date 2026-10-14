using System;
using System.IO;
using System.Text.Json;
public class Program { public static void Main(string[] args){using var output=new StreamWriter(args[1]);foreach(string line in File.ReadLines(args[0]))output.WriteLine(Pressure.Side(JsonSerializer.Deserialize<double[][]>(line)));}}
