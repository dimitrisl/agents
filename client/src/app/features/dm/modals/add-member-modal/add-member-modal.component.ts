import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
  ForgeTab,
  ForgeTabsComponent,
} from '../../../../shared/ui';

type AddMemberTab = 'existing' | 'custom' | 'invite';

@Component({
  selector: 'app-add-member-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
    ForgeTabsComponent,
  ],
  templateUrl: './add-member-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AddMemberModalComponent {
  readonly addMemberTabs: ForgeTab[] = [
    { id: 'existing', label: '📜 Vault Heroes' },
    { id: 'custom', label: '✏️ Custom Hero' },
    { id: 'invite', label: '🔑 Invite Code' },
  ];

  @Input() open = false;
  @Input() campaignName = '';
  @Input() addMemberTab: AddMemberTab = 'existing';
  @Input() selectedExistingCharId = '';
  @Input() filteredCharacters: any[] = [];
  @Input() selectedHero: any = null;
  @Input() newMemberName = '';
  @Input() newMemberClass = 'Fighter';
  @Input() newMemberLevel = 5;
  @Input() newMemberHp = 40;
  @Input() newMemberAc = 16;
  @Input() inviteCode = '';

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() addMemberTabChange = new EventEmitter<AddMemberTab>();
  @Output() selectedExistingCharIdChange = new EventEmitter<string>();
  @Output() newMemberNameChange = new EventEmitter<string>();
  @Output() newMemberClassChange = new EventEmitter<string>();
  @Output() newMemberLevelChange = new EventEmitter<number>();
  @Output() newMemberHpChange = new EventEmitter<number>();
  @Output() newMemberAcChange = new EventEmitter<number>();
  @Output() addExistingPartyMember = new EventEmitter<void>();
  @Output() addPartyMember = new EventEmitter<void>();
  @Output() copyInviteCode = new EventEmitter<void>();

  selectAddMemberTab(tabId: string): void {
    if (tabId === 'existing' || tabId === 'custom' || tabId === 'invite') {
      this.addMemberTabChange.emit(tabId);
    }
  }
}
