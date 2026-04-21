from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.db.models import Sum, Min
from .models import Council, Contractor, Project, Bid, Package
import datetime

class ContractorRegisterForm(UserCreationForm):
    name = forms.CharField(max_length=100)
    contact = forms.CharField(max_length=100)
    contact_email = forms.EmailField()
    experience = forms.IntegerField()
    role = forms.CharField(max_length=100)

    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def clean_experience(self):
        experience = self.cleaned_data.get('experience')
        if experience and experience > 50:
            raise forms.ValidationError('Experience cannot exceed 50 years.')
        if experience and experience < 0:
            raise forms.ValidationError('Experience cannot be negative.')
        return experience

    def clean_contact_email(self):
        email = self.cleaned_data.get('contact_email')
        if Contractor.objects.filter(contact_email=email).exists():
            raise forms.ValidationError('A contractor with this email already exists.')
        return email

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'budget', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter project title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe the project scope, requirements, and objectives...',
                'rows': 5
            }),
            'budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter total budget',
                'min': 1
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        labels = {
            'title': 'Project Title',
            'description': 'Project Description',
            'budget': 'Total Budget (NPR)',
            'start_date': 'Start Date',
            'end_date': 'End Date',
        }
        help_texts = {
            'budget': 'This will be divided into packages for contractors to bid on.',
            'description': 'Provide detailed information about what the project entails.',
        }

    def clean_budget(self):
        budget = self.cleaned_data.get('budget')

        if budget and budget <= 0:
            raise forms.ValidationError('Budget must be a positive number.')

        if self.instance and self.instance.pk:
            allocated = Package.objects.filter(
                project=self.instance
            ).aggregate(total=Sum('budget'))['total'] or 0

            if allocated > 0 and budget < allocated:
                raise forms.ValidationError(
                    f'Cannot reduce budget below allocated amount. '
                    f'Already allocated to packages: Rs {allocated:,}. '
                    f'Minimum budget: Rs {allocated:,}'
                )

        return budget

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if end_date <= start_date:
                raise forms.ValidationError('End date must be after start date.')

            if not self.instance.pk and start_date < datetime.date.today():
                raise forms.ValidationError('Start date cannot be in the past.')

        return cleaned_data

class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['title', 'description', 'budget']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Foundation and Structural Work',
                'maxlength': '100',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea',
                'placeholder': 'Describe the scope of work, deliverables, and any specific requirements for this package...',
                'rows': 6,
            }),
            'budget': forms.NumberInput(attrs={
                'class': 'form-input with-prefix',
                'placeholder': '1000000',
                'min': '1',
            }),
        }
        labels = {
            'title': 'Package Title',
            'description': 'Package Description',
            'budget': 'Package Budget (£)',
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project

        for field in self.fields.values():
            field.required = True

        if self.project:
            self.fields['budget'].widget.attrs['max'] = self.project.budget

        if self.instance and self.instance.pk:
            self.original_budget = self.instance.budget
        else:
            self.original_budget = 0

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title or not title.strip():
            raise forms.ValidationError('Package title cannot be empty.')
        return title.strip()

    def clean_description(self):
        description = self.cleaned_data.get('description')
        if not description or not description.strip():
            raise forms.ValidationError('Package description cannot be empty.')
        return description.strip()

    def clean_budget(self):
        budget = self.cleaned_data.get('budget')

        if budget is None:
            raise forms.ValidationError('Budget is required.')

        if budget <= 0:
            raise forms.ValidationError('Budget must be greater than 0.')

        if self.project:
            if budget > self.project.budget:
                raise forms.ValidationError(
                    f'Package budget cannot exceed project budget of £ {self.project.budget:,}'
                )

            if self.instance and self.instance.pk:
                bid_count = self.instance.bids.count()

                if bid_count > 0 and budget < self.original_budget:
                    raise forms.ValidationError(
                        f'Cannot decrease budget. This package has {bid_count} bid(s). '
                        f'Original budget: Rs {self.original_budget:,}. '
                        f'Decreasing budget after bids are placed is unfair to contractors.'
                    )

                if bid_count > 0:
                    lowest_bid = self.instance.bids.aggregate(
                        lowest=Min('amount')
                    )['lowest']

                    if lowest_bid and budget < lowest_bid:
                        raise forms.ValidationError(
                            f'Budget cannot be less than lowest bid of Rs {lowest_bid:,}'
                        )

            other_packages_total = Package.objects.filter(
                project=self.project
            ).exclude(
                id=self.instance.id if self.instance.pk else None
            ).aggregate(
                total=Sum('budget')
            )['total'] or 0

            total_after_adding = other_packages_total + budget

            if total_after_adding > self.project.budget:
                remaining = self.project.budget - other_packages_total
                raise forms.ValidationError(
                    f'Adding this package would exceed project budget. '
                    f'Project budget: Rs {self.project.budget:,} | '
                    f'Already allocated: Rs {other_packages_total:,} | '
                    f'Remaining available: Rs {remaining:,}'
                )

        return budget

class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount', 'document1', 'document2', 'document3']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-input with-prefix',
                'placeholder': 'Enter your bid amount',
                'min': '1',
                'step': '0.01',
            }),
            'document1': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            }),
            'document2': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            }),
            'document3': forms.FileInput(attrs={
                'class': 'form-file-input',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
            }),
        }
        labels = {
            'amount': 'Bid Amount (£)',
            'document1': 'Document 1 (Optional)',
            'document2': 'Document 2 (Optional)',
            'document3': 'Document 3 (Optional)',
        }

    def __init__(self, *args, package=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.package = package

        self.fields['amount'].required = True

        self.fields['document1'].required = False
        self.fields['document2'].required = False
        self.fields['document3'].required = False

        if self.package:
            self.fields['amount'].widget.attrs['max'] = self.package.budget

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')

        if amount is None:
            raise forms.ValidationError('Bid amount is required.')

        if amount <= 0:
            raise forms.ValidationError('Bid amount must be greater than 0.')

        if self.package:
            if amount > self.package.budget:
                raise forms.ValidationError(
                    f'Bid amount cannot exceed package budget of £ {self.package.budget:,.2f}'
                )

            if self.package.has_approved_bid():
                raise forms.ValidationError(
                    'This package already has an approved bid. Bidding is closed.'
                )

        return amount

    def clean(self):
        cleaned_data = super().clean()

        if self.instance and self.instance.pk:
            if self.instance.status != 'pending':
                raise forms.ValidationError(
                    f'Cannot edit {self.instance.status} bid. Only pending bids can be modified.'
                )

        files = [
            cleaned_data.get('document1'),
            cleaned_data.get('document2'),
            cleaned_data.get('document3')
        ]

        for file in files:
            if file:
                if file.size > 10 * 1024 * 1024:
                    raise forms.ValidationError(
                        f'File "{file.name}" exceeds 10MB limit.'
                    )

                allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
                file_name_lower = file.name.lower()
                file_ext = file_name_lower[file_name_lower.rfind('.'):]

                if file_ext not in allowed_extensions:
                    raise forms.ValidationError(
                        f'File "{file.name}" has invalid type. '
                        f'Allowed formats: PDF, DOC, DOCX, JPG, PNG'
                    )

        return cleaned_data

class CouncilProfileForm(forms.ModelForm):
    class Meta:
        model = Council
        fields = ['name', 'contact', 'contact_email']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Council Name'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contact Number'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contact Email'
            }),
        }
        labels = {
            'name': 'Council Name',
            'contact': 'Contact Number',
            'contact_email': 'Contact Email',
        }


class ContractorProfileForm(forms.ModelForm):
    class Meta:
        model = Contractor
        fields = ['name', 'contact', 'contact_email', 'experience', 'role']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contractor Name'
            }),
            'contact': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contact Number'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Contact Email'
            }),
            'experience': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Years of Experience',
                'min': '0',
                'max': '50'
            }),
            'role': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Role/Specialization'
            }),
        }
        labels = {
            'name': 'Contractor Name',
            'contact': 'Contact Number',
            'contact_email': 'Contact Email',
            'experience': 'Years of Experience',
            'role': 'Role/Specialization',
        }

    def clean_experience(self):
        experience = self.cleaned_data.get('experience')
        if experience and experience > 50:
            raise forms.ValidationError('Experience cannot exceed 50 years.')
        if experience and experience < 0:
            raise forms.ValidationError('Experience cannot be negative.')
        return experience


class CustomPasswordChangeForm(PasswordChangeForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Current Password'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'New Password'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm New Password'
        })

        self.fields['old_password'].label = 'Current Password'
        self.fields['new_password1'].label = 'New Password'
        self.fields['new_password2'].label = 'Confirm New Password'

class CouncilAdminForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        help_text="Username for login"
    )
    email = forms.EmailField(
        required=False,
        help_text="Email address (optional)"
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=True,
        help_text="Password for the user account"
    )

    class Meta:
        model = Council
        fields = ['name', 'contact', 'contact_email', 'slug']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['email'].initial = self.instance.user.email
            self.fields['password'].required = False
            self.fields['password'].help_text = "Leave blank to keep current password"

    def clean_username(self):
        username = self.cleaned_data.get('username')

        if not self.instance.pk:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError('This username already exists.')

        elif self.instance.user:
            if User.objects.filter(username=username).exclude(pk=self.instance.user.pk).exists():
                raise forms.ValidationError('This username already exists.')

        return username

    def save(self, commit=True):
        council = super().save(commit=False)

        if not council.user_id:
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data.get('email', ''),
                password=self.cleaned_data['password']
            )
            council.user = user
        else:
            user = council.user
            user.username = self.cleaned_data['username']
            user.email = self.cleaned_data.get('email', '')

            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])

            user.save()

        if commit:
            council.save()

        return council