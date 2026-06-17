#!/usr/bin/env python3
"""Integration test script for VividWrite 2.0."""

import requests
import json

# 测试数据
test_data = {
    "chart_type": "bar",
    "requirement": "Summarise the information by selecting and reporting the main features, and make comparisons where relevant. Write at least 150 words.",
    "student_answer": """
    The given chart depicts the time Australian residents spent on varying types of telephone calls between 2001 and 2008.

    Local fixed line calls were the highest throughout this period, upsurging from 72 billion minutes to under 90 billion in 2003. Following year, this figure peaked at 90 billion. 
    Post this, by 2008, it had a downtrend and fell back to the figure of 2001. Both national and international fixed line calls grew gradually from 38 billion to 61 billion toward the end of the period in question. However, the progress decelerated over the last two years.

    Also, dramatic growth can be seen in mobile calls from 2 billion to 46 billion minutes. This increase was specifically noticed between 2005 and 2008. During this time, the mobile phone's use got tripled. In 2008, although local fixed line calls were still popular, the gap between these three categories narrowed significantly over the second half of this period.
    """,
    "deplot_text": "TITLE | Australia telephone calls by category from 2001-2008<0x0A>Year | Local fixed line calls | National and international fixed line calls | Mobile calls<0x0A>2001 | 73 | 38 | 3<0x0A>2002 | 78 | 40 | 6<0x0A>2003 | 83 | 42 | 10<0x0A>2004 | 88 | 45 | 12<0x0A>2005 | 90 | 47 | 15<0x0A>2006 | 85 | 50 | 23<0x0A>2007 | 78 | 52 | 38<0x0A>2008 | 73 | 58 | 48"
}

def test_api():
    """Test API endpoints."""
    base_url = "http://localhost:8000"
    
    print("🚀 Starting integration test for VividWrite 2.0 ...")
    print("📋 UI includes three primary tabs:")
    print("   1. Flowchart - writing structure guidance")
    print("   2. Visual Feedback - chart visualization")
    print("   3. Revision Suggestions - improvement advice")
    
    # 测试健康检查
    print("\n1. Testing health endpoint ...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend service. Ensure it is running.")
        print("   Try: cd backend && uvicorn main:app --reload")
        return
    
    # 测试图表分析API
    print("\n2. Testing chart analysis API ...")
    try:
        response = requests.post(
            f"{base_url}/api/analyze-chart",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Chart analysis API call succeeded")
                print(f"   Chart type: {result.get('chart_data', {}).get('chart_type', 'N/A')}")
                print(f"   Chart title: {result.get('chart_data', {}).get('title', 'N/A')}")
                print(f"   Revision suggestions count: {len(result.get('revision_suggestions', []))}")
                
                # 显示修订建议
                suggestions = result.get('revision_suggestions', [])
                if suggestions:
                    print("\n   Revision Suggestions:")
                    for i, suggestion in enumerate(suggestions, 1):
                        print(f"   {i}. [{suggestion.get('type', 'unknown')}] {suggestion.get('message', '')}")
            else:
                print(f"❌ Chart analysis failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
    
    print("\n🎉 Test complete!")

if __name__ == "__main__":
    test_api()
