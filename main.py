import streamlit as st
import os
import psutil
import platform
import sys
from datetime import datetime


current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)


from app.chat_interface import ChatInterface
from app.log_processor import LogProcessor
from app.knowledge_base import KnowledgeBase

# Page configuration
st.set_page_config(
    page_title="AI Log Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

class LogAnalyzerApp:
    def __init__(self):
        self.chat_interface = ChatInterface()
        self.log_processor = LogProcessor()
        self.knowledge_base = KnowledgeBase()
        
    def run(self):
        st.title("🔍 AI Log Analyzer Assistant")
        
        # Sidebar
        with st.sidebar:
            st.header("Configuration")
            
            # Model selection
            model_choice = st.selectbox(
                "Select AI Model",
                ["llama2:7b", "codellama:13b", "mistral:7b"]
            )
            
            # File upload
            uploaded_file = st.file_uploader(
                "Upload Log File",
                type=['log', 'txt', 'json', 'xml']
            )
            
            # System info
            st.header("System Analysis")
            if st.button("Analyze System"):
                system_report = self.show_system_analysis()
                # Append this report as a message from the assistant
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": system_report
                })
                
        
        # Main chat interface
        self.render_chat_interface(uploaded_file, model_choice)
        
    def show_system_analysis(self):
      # Collect system info
      sys_info = {
          "Platform": platform.system(),
          "Platform Version": platform.version(),
          "CPU Cores": psutil.cpu_count(logical=False),
          "Total Memory (GB)": round(psutil.virtual_memory().total / (1024 ** 3), 2),
          "Available Memory (GB)": round(psutil.virtual_memory().available / (1024 ** 3), 2),
          "Disk Usage": {},
          "Running Processes": len(psutil.pids()),
          "Boot Time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
      }
  
      # Disk usage
      disk_usage = psutil.disk_usage("/")
      sys_info["Disk Usage"] = {
          "Total (GB)": round(disk_usage.total / (1024 ** 3), 2),
          "Used (GB)": round(disk_usage.used / (1024 ** 3), 2),
          "Free (GB)": round(disk_usage.free / (1024 ** 3), 2),
          "Percent Used": disk_usage.percent,
      }
  
      # Top 5 processes
      processes = sorted(psutil.process_iter(['pid', 'name', 'memory_info']),
                         key=lambda p: p.info['memory_info'].rss,
                         reverse=True)[:5]
  
      # Build output string
      output = ""
      output += f"### System Information\n"
      output += f"- Platform: {sys_info['Platform']} {sys_info['Platform Version']}\n"
      output += f"- CPU Cores: {sys_info['CPU Cores']}\n"
      output += f"- Total Memory: {sys_info['Total Memory (GB)']} GB\n"
      output += f"- Available Memory: {sys_info['Available Memory (GB)']} GB\n"
      output += f"- Boot Time: {sys_info['Boot Time']}\n"
      output += f"- Number of Processes: {sys_info['Running Processes']}\n"
      output += "Disk Usage:\n"
      for key, value in sys_info["Disk Usage"].items():
          if 'GB' in key:
              output += f"  - {key}: {value} GB\n"
          else:
              output += f"  - {key}: {value}\n"
      output += "Top 5 Processes by Memory Usage:\n"
      for proc in processes:
          output += f"  - PID: {proc.info['pid']} | Name: {proc.info['name']} | RSS: {round(proc.info['memory_info'].rss / (1024 ** 2), 2)} MB\n"
  
      return output


    
    def render_chat_interface(self, uploaded_file, model_choice):
        # Chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # File processing
        if uploaded_file:
            with st.chat_message("assistant"):
                st.markdown("📁 Processing uploaded log file...")
                analysis_results = self.log_processor.process_file(uploaded_file)
                st.markdown(f"**Analysis Complete:** {analysis_results['summary']}")
        
        # Chat input
        if prompt := st.chat_input("Ask about your logs or system issues..."):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = self.chat_interface.generate_response(
                        prompt, model_choice, uploaded_file
                    )
                    st.markdown(response)
            
            # Add assistant response
            st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    app = LogAnalyzerApp()
    app.run()
