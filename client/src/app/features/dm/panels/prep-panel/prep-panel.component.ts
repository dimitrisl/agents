import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeTextareaDirective } from '../../../../shared/ui';
import { SessionService } from '../../../../core/services/session.service';
import { SessionLog, SessionPrep } from '../../../../core/models/session.model';

@Component({
  selector: 'app-prep-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective, ForgeTextareaDirective],
  templateUrl: './prep-panel.component.html',
})
export class PrepPanelComponent implements OnInit {
  @Input() campaignName!: string;

  sessions: SessionLog[] = [];
  prepResult: SessionPrep | null = null;

  isGeneratingPrep = false;
  isUploadingAudio = false;

  dmIdeas = '';
  newSessionNumber = 1;
  selectedFile: File | null = null;

  journeyGraph: import('../../../../core/models/session.model').JourneyGraph | null = null;
  isGeneratingJourney = false;

  constructor(private sessionService: SessionService) {}

  ngOnInit(): void {
    if (this.campaignName) {
      this.loadSessions();
    }
  }

  loadSessions(): void {
    this.sessionService.getSessions(this.campaignName).subscribe({
      next: (res) => {
        this.sessions = res;
        if (this.sessions.length > 0) {
          this.newSessionNumber = this.sessions[0].session_number + 1;
        }
      },
      error: (err) => console.error('Failed to load sessions', err)
    });
  }

  onFileSelected(event: any): void {
    const file: File = event.target.files[0];
    if (file) {
      this.selectedFile = file;
    }
  }

  uploadAudio(): void {
    if (!this.selectedFile) return;

    this.isUploadingAudio = true;
    this.sessionService.uploadAudioSession(this.campaignName, this.newSessionNumber, this.selectedFile).subscribe({
      next: (res) => {
        this.isUploadingAudio = false;
        this.selectedFile = null;
        this.loadSessions(); // Reload to see the new session
      },
      error: (err) => {
        console.error('Failed to upload audio', err);
        this.isUploadingAudio = false;
      }
    });
  }

  generatePrep(): void {
    this.isGeneratingPrep = true;
    this.sessionService.generateSessionPrep(this.campaignName, this.dmIdeas).subscribe({
      next: (res) => {
        this.prepResult = res;
        this.isGeneratingPrep = false;
      },
      error: (err) => {
        console.error('Failed to generate prep', err);
        this.isGeneratingPrep = false;
      }
    });
  }

  generateJourney(): void {
    this.isGeneratingJourney = true;
    this.sessionService.generateJourneyGraph(this.campaignName).subscribe({
      next: (res) => {
        this.journeyGraph = res;
        this.isGeneratingJourney = false;
      },
      error: (err) => {
        console.error('Failed to generate journey', err);
        this.isGeneratingJourney = false;
      }
    });
  }
}
