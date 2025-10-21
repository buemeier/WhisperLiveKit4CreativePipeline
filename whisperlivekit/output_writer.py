"""
Output writer for saving transcriptions and audio to files.
"""

import os
import json
import wave
import logging
from datetime import datetime
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class OutputWriter:
    """Handles writing transcription and audio data to files."""
    
    def __init__(self, output_dir: str, save_transcript: bool = False, 
                 save_audio: bool = False, transcript_format: str = "txt",
                 sample_rate: int = 16000):
        """
        Initialize the output writer.
        
        Args:
            output_dir: Directory to save output files
            save_transcript: Whether to save transcriptions
            save_audio: Whether to save audio
            transcript_format: Format for transcripts (txt, json, srt, all)
            sample_rate: Audio sample rate for WAV files
        """
        self.output_dir = output_dir
        self.save_transcript = save_transcript
        self.save_audio = save_audio
        self.transcript_format = transcript_format
        self.sample_rate = sample_rate
        
        # Create session-based subdirectory with timestamp
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(output_dir, f"session_{self.session_timestamp}")
        
        # Initialize file handles and buffers
        self.audio_file = None
        self.audio_buffer = bytearray()
        self.transcript_lines = []
        
        if save_transcript or save_audio:
            self._setup_output_directory()
    
    def _setup_output_directory(self):
        """Create output directory if it doesn't exist."""
        try:
            Path(self.session_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory created: {self.session_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory {self.session_dir}: {e}")
            raise
    
    def write_audio_chunk(self, audio_data: bytes):
        """
        Append audio data to buffer for later writing.
        
        Args:
            audio_data: Raw PCM audio bytes (16-bit signed little-endian)
        """
        if self.save_audio:
            self.audio_buffer.extend(audio_data)
    
    def add_transcript_line(self, line_dict: dict):
        """
        Add a transcription line to the buffer.
        
        Args:
            line_dict: Dictionary with keys: speaker, text, start, end, (optional) translation
        """
        if self.save_transcript:
            # Only add if this is a new line or an update to the last line
            if not self.transcript_lines or self.transcript_lines[-1] != line_dict:
                # Check if we're updating the last line (same speaker and overlapping time)
                if self.transcript_lines and \
                   self.transcript_lines[-1].get('speaker') == line_dict.get('speaker') and \
                   self.transcript_lines[-1].get('end') == line_dict.get('start'):
                    # Update the last line
                    self.transcript_lines[-1]['text'] += ' ' + line_dict.get('text', '')
                    self.transcript_lines[-1]['end'] = line_dict.get('end')
                else:
                    # Add as new line
                    self.transcript_lines.append(line_dict.copy())
    
    def _write_txt(self):
        """Write transcript as plain text file."""
        txt_path = os.path.join(self.session_dir, "transcript.txt")
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                for line in self.transcript_lines:
                    speaker = line.get('speaker', 1)
                    text = line.get('text', '').strip()
                    if text:  # Only write non-empty lines
                        f.write(f"Speaker {speaker}: {text}\n")
            logger.info(f"Transcript saved to {txt_path}")
        except Exception as e:
            logger.error(f"Failed to write TXT transcript: {e}")
    
    def _write_json(self):
        """Write transcript as JSON file with full metadata."""
        json_path = os.path.join(self.session_dir, "transcript.json")
        try:
            output_data = {
                "session_timestamp": self.session_timestamp,
                "lines": self.transcript_lines
            }
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Transcript saved to {json_path}")
        except Exception as e:
            logger.error(f"Failed to write JSON transcript: {e}")
    
    def _write_srt(self):
        """Write transcript as SRT subtitle file."""
        srt_path = os.path.join(self.session_dir, "transcript.srt")
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                for idx, line in enumerate(self.transcript_lines, 1):
                    text = line.get('text', '').strip()
                    if not text:
                        continue
                    
                    # Format: HH:MM:SS -> needs conversion from HH:MM:SS to HH:MM:SS,mmm
                    start_time = self._format_srt_time(line.get('start', '0:00:00'))
                    end_time = self._format_srt_time(line.get('end', '0:00:00'))
                    speaker = line.get('speaker', 1)
                    
                    f.write(f"{idx}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"Speaker {speaker}: {text}\n")
                    f.write("\n")
            logger.info(f"Transcript saved to {srt_path}")
        except Exception as e:
            logger.error(f"Failed to write SRT transcript: {e}")
    
    def _format_srt_time(self, time_str: str) -> str:
        """
        Convert time string from HH:MM:SS to SRT format HH:MM:SS,mmm.
        
        Args:
            time_str: Time string in format HH:MM:SS or H:MM:SS
        
        Returns:
            Time string in SRT format
        """
        # Parse the time string
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            # Ensure two-digit format
            hours = hours.zfill(2)
            minutes = minutes.zfill(2)
            seconds = seconds.zfill(2)
            return f"{hours}:{minutes}:{seconds},000"
        return "00:00:00,000"
    
    def _write_wav(self):
        """Write accumulated audio buffer as WAV file."""
        if not self.audio_buffer:
            logger.warning("No audio data to save")
            return
        
        wav_path = os.path.join(self.session_dir, "recording.wav")
        try:
            with wave.open(wav_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(bytes(self.audio_buffer))
            logger.info(f"Audio saved to {wav_path}")
        except Exception as e:
            logger.error(f"Failed to write WAV audio: {e}")
    
    def finalize(self):
        """Write all accumulated data to files."""
        if self.save_transcript and self.transcript_lines:
            if self.transcript_format == "txt" or self.transcript_format == "all":
                self._write_txt()
            if self.transcript_format == "json" or self.transcript_format == "all":
                self._write_json()
            if self.transcript_format == "srt" or self.transcript_format == "all":
                self._write_srt()
        
        if self.save_audio and self.audio_buffer:
            self._write_wav()
    
    def cleanup(self):
        """Clean up resources."""
        if self.audio_file:
            self.audio_file.close()
            self.audio_file = None
