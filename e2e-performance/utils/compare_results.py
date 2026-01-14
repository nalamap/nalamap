#!/usr/bin/env python3
"""
Compare baseline vs streaming performance results.
"""
from pathlib import Path
import re


def parse_results_file(filepath: Path) -> dict:
    """Parse a results file and extract metrics."""
    results = {}
    
    with open(filepath, "r") as f:
        content = f.read()
    
    # Extract configuration
    config_match = re.search(r"Configuration: (.+)\n", content)
    config = config_match.group(1) if config_match else "Unknown"
    
    # Extract file results
    file_blocks = re.findall(
        r"(\d+_\w+\.geojson) \((.+?) MB\)\n-+\n"
        r"Success Rate: (.+?)%\n"
        r"Average Time: (.+?)s\n"
        r"Average TTFB: (.+?)s\n"
        r"Average Rate: (.+?) MB/s\n",
        content
    )
    
    for filename, size, success, time, ttfb, rate in file_blocks:
        results[filename] = {
            "size_mb": float(size),
            "success_rate": float(success),
            "avg_time": float(time),
            "avg_ttfb": float(ttfb),
            "avg_rate": float(rate),
        }
    
    return {
        "config": config,
        "files": results
    }


def main():
    results_dir = Path(__file__).parent.parent / "results"
    
    baseline_file = results_dir / "baseline_results.txt"
    streaming_file = results_dir / "streaming_results.txt"
    
    if not baseline_file.exists():
        print("❌ Baseline results not found!")
        return
    
    if not streaming_file.exists():
        print("❌ Streaming results not found!")
        return
    
    baseline = parse_results_file(baseline_file)
    streaming = parse_results_file(streaming_file)
    
    # Create comparison report
    output_file = results_dir / "performance_comparison.txt"
    
    with open(output_file, "w") as f:
        f.write("PERFORMANCE COMPARISON REPORT\n")
        f.write("=" * 90 + "\n\n")
        
        f.write(f"BASELINE:  {baseline['config']}\n")
        f.write(f"STREAMING: {streaming['config']}\n\n")
        
        f.write("=" * 90 + "\n")
        f.write(
            f"{'File':<35} {'Size':<10} {'Baseline':<15} "
            f"{'Streaming':<15} {'Improvement':<15}\n"
        )
        f.write("=" * 90 + "\n")
        
        total_baseline_rate = 0
        total_streaming_rate = 0
        count = 0
        
        for filename in sorted(baseline["files"].keys()):
            if filename not in streaming["files"]:
                continue
            
            b = baseline["files"][filename]
            s = streaming["files"][filename]
            
            improvement = ((s["avg_rate"] - b["avg_rate"]) / b["avg_rate"]) * 100
            
            size_str = f"{b['size_mb']:.2f} MB"
            baseline_str = f"{b['avg_rate']:.1f} MB/s"
            streaming_str = f"{s['avg_rate']:.1f} MB/s"
            improvement_str = f"{improvement:+.1f}%"
            
            f.write(
                f"{filename:<35} {size_str:<10} {baseline_str:<15} "
                f"{streaming_str:<15} {improvement_str:<15}\n"
            )
            
            total_baseline_rate += b["avg_rate"]
            total_streaming_rate += s["avg_rate"]
            count += 1
        
        f.write("=" * 90 + "\n")
        
        avg_baseline = total_baseline_rate / count if count > 0 else 0
        avg_streaming = total_streaming_rate / count if count > 0 else 0
        avg_improvement = (
            ((avg_streaming - avg_baseline) / avg_baseline) * 100
            if avg_baseline > 0
            else 0
        )
        
        f.write(
            f"{'AVERAGE':<35} {'':<10} {avg_baseline:<15.1f} "
            f"{avg_streaming:<15.1f} {avg_improvement:+15.1f}%\n"
        )
        f.write("=" * 90 + "\n\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 90 + "\n")
        f.write(f"Average Baseline Speed:  {avg_baseline:.1f} MB/s\n")
        f.write(f"Average Streaming Speed: {avg_streaming:.1f} MB/s\n")
        f.write(f"Average Improvement:     {avg_improvement:+.1f}%\n\n")
        
        # Find best improvements
        improvements = []
        for filename in baseline["files"]:
            if filename not in streaming["files"]:
                continue
            b = baseline["files"][filename]
            s = streaming["files"][filename]
            improvement = ((s["avg_rate"] - b["avg_rate"]) / b["avg_rate"]) * 100
            improvements.append((filename, improvement, b["size_mb"]))
        
        improvements.sort(key=lambda x: x[1], reverse=True)
        
        f.write("TOP 3 IMPROVEMENTS\n")
        f.write("-" * 90 + "\n")
        for i, (filename, improvement, size) in enumerate(improvements[:3], 1):
            f.write(
                f"{i}. {filename} ({size:.2f} MB): "
                f"{improvement:+.1f}% faster\n"
            )
    
    print(f"\n✅ Comparison report saved to: {output_file}\n")
    
    # Print summary to console
    print("=" * 90)
    print("PERFORMANCE COMPARISON SUMMARY")
    print("=" * 90)
    print(f"Average Baseline Speed:  {avg_baseline:.1f} MB/s")
    print(f"Average Streaming Speed: {avg_streaming:.1f} MB/s")
    print(f"Average Improvement:     {avg_improvement:+.1f}%")
    print("=" * 90)
    
    if avg_improvement > 0:
        print(f"\n✅ Streaming endpoint is {avg_improvement:.1f}% faster on average!")
    else:
        print(
            f"\n⚠️  Streaming endpoint is {avg_improvement:.1f}% slower on average."
        )


if __name__ == "__main__":
    main()
