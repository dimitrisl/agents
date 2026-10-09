import { Component, Input, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeTextareaDirective } from '../../../../shared/ui';
import { SessionService } from '../../../../core/services/session.service';
import { SessionLog, SessionPrep } from '../../../../core/models/session.model';
import { CampaignPlotService } from '../../../../core/services/campaign-plot.service';
import { CampaignSkeleton } from '../../../../core/models/campaign-skeleton.model';
import { RollToastService } from '../../../../core/services/roll-toast.service';

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
  skeleton: CampaignSkeleton | null = null;

  isGeneratingPrep = false;
  isProcessingSession = false;
  isGeneratingOutlines = false;

  dmIdeas = '';
  sessionTextNotes = '';
  newSessionNumber = 1;
  selectedFile: File | null = null;

  journeyGraph: import('../../../../core/models/session.model').JourneyGraph | null = null;
  isGeneratingJourney = false;

  constructor(
    private sessionService: SessionService,
    private plotService: CampaignPlotService,
    private rollToast: RollToastService
  ) {}

  ngOnInit(): void {
    if (this.campaignName) {
      this.loadSessions();
      this.loadSkeleton();
    }
  }

  loadSkeleton(): void {
    this.plotService.getSkeleton(this.campaignName).subscribe({
      next: (res) => this.skeleton = res,
      error: (err) => {
        console.error('Failed to load skeleton', err);
        this.rollToast.showMessage('⚠️ LOAD FAILED', 'Failed to load campaign skeleton.');
      }
    });
  }

  saveSkeleton(): void {
    if (!this.skeleton) return;
    this.plotService.updateSkeleton(this.campaignName, this.skeleton).subscribe({
      next: (res) => {
        this.skeleton = res;
        this.rollToast.showMessage('✅ SAVED', 'Campaign skeleton saved successfully.');
      },
      error: (err) => {
        console.error('Failed to save skeleton', err);
        this.rollToast.showMessage('⚠️ SAVE FAILED', 'Failed to save campaign skeleton.');
      }
    });
  }

  generateOutlines(): void {
    if (!this.skeleton) return;
    this.isGeneratingOutlines = true;

    // First save the current state, then generate
    this.plotService.updateSkeleton(this.campaignName, this.skeleton).subscribe({
      next: () => {
        this.plotService.generateOutlines(this.campaignName).subscribe({
          next: (res) => {
            this.skeleton = res;
            this.isGeneratingOutlines = false;
            this.rollToast.showMessage('✅ OUTLINES GENERATED', 'Session outlines generated successfully.');
          },
          error: (err) => {
            console.error('Failed to generate outlines', err);
            this.isGeneratingOutlines = false;
            this.rollToast.showMessage('⚠️ GENERATION FAILED', 'Failed to generate session outlines.');
          }
        });
      },
      error: (err) => {
        console.error('Failed to save before generating', err);
        this.isGeneratingOutlines = false;
        this.rollToast.showMessage('⚠️ SAVE FAILED', 'Failed to save skeleton before generating outlines.');
      }
    });
  }

  loadSessions(): void {
    this.sessionService.getSessions(this.campaignName).subscribe({
      next: (res) => {
        this.sessions = res;
        if (this.sessions.length > 0) {
          this.newSessionNumber = this.sessions[0].session_number + 1;
        }
      },
      error: (err) => {
        console.error('Failed to load sessions', err);
        this.rollToast.showMessage('⚠️ LOAD FAILED', 'Failed to load session logs.');
      }
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

    this.isProcessingSession = true;
    this.sessionService.uploadAudioSession(this.campaignName, this.newSessionNumber, this.selectedFile).subscribe({
      next: (res) => {
        this.isProcessingSession = false;
        this.selectedFile = null;
        this.loadSessions(); // Reload to see the new session
        this.rollToast.showMessage('🎙️ AUDIO PROCESSED', 'Audio session processed successfully.');
      },
      error: (err) => {
        console.error('Failed to upload audio', err);
        this.isProcessingSession = false;
        this.rollToast.showMessage('⚠️ PROCESS FAILED', 'Failed to process audio session.');
      }
    });
  }

  processTextSession(): void {
    if (!this.sessionTextNotes) return;

    this.isProcessingSession = true;
    this.sessionService.processTextSession(this.campaignName, this.newSessionNumber, this.sessionTextNotes).subscribe({
      next: (res) => {
        this.isProcessingSession = false;
        this.sessionTextNotes = '';
        this.loadSessions(); // Reload to see the new session
        this.rollToast.showMessage('📝 NOTES PROCESSED', 'Text notes processed successfully.');
      },
      error: (err) => {
        console.error('Failed to process text notes', err);
        this.isProcessingSession = false;
        this.rollToast.showMessage('⚠️ PROCESS FAILED', 'Failed to process text notes.');
      }
    });
  }

  generatePrep(): void {
    this.isGeneratingPrep = true;
    this.sessionService.generateSessionPrep(this.campaignName, this.dmIdeas).subscribe({
      next: (res) => {
        this.prepResult = res;
        this.isGeneratingPrep = false;
        this.rollToast.showMessage('✅ PREP READY', 'Session prep generated successfully.');
      },
      error: (err) => {
        console.error('Failed to generate prep', err);
        this.isGeneratingPrep = false;
        this.rollToast.showMessage('⚠️ PREP FAILED', 'Failed to generate session prep.');
      }
    });
  }

  generateJourney(): void {
    this.isGeneratingJourney = true;
    this.sessionService.generateJourneyGraph(this.campaignName).subscribe({
      next: (res) => {
        this.journeyGraph = res;
        this.isGeneratingJourney = false;
        this.rollToast.showMessage('🗺️ JOURNEY READY', 'Journey graph generated successfully.');
      },
      error: (err) => {
        console.error('Failed to generate journey', err);
        this.isGeneratingJourney = false;
        this.rollToast.showMessage('⚠️ JOURNEY FAILED', 'Failed to generate journey graph.');
      }
    });
  }
}
