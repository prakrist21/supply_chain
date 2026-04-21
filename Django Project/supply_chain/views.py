from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .forms import ProjectForm, PackageForm
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, TemplateView, DetailView, ListView, UpdateView, DeleteView
from supply_chain.forms import ContractorRegisterForm, BidForm, CouncilProfileForm, ContractorProfileForm, CustomPasswordChangeForm
from supply_chain.models import Council, Contractor, Project, Bid, Team, Package, Activity
from django.db.models import Count, Sum, Q, Min, F, Avg
import datetime
from django.utils import timezone
from django.db import transaction
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io
from django.core.paginator import Paginator
from django.contrib import messages

def hello_world_index(request):
    return HttpResponse("Hello World! This is the main index of the Suppy Chain project")

def landing_page(request):
    return render(request, 'supply_chain/landing_page.html')

def all_councils(request):
    councils = Council.objects.all()

    context = {
        'councils': councils,
    }

    return render(request, 'supply_chain/all_councils_list.html', context)

class UserLogin(LoginView):
    template_name = 'supply_chain/login.html'
    def form_valid(self, form):
        response = super().form_valid(form)
        role = self.request.POST.get('role')
        user = self.request.user

        if role == "contractor" and hasattr(user, "contractor"):
            return redirect("contractorDashboard")
        elif role == "council" and hasattr(user, "council"):
            return redirect("councilDashboard")
        else:
            messages.error(self.request, "Role mismatch or profile not found.")
            return redirect("login")

    def form_invalid(self, form):
        messages.error(self.request, "Invalid username or password.")
        return super().form_invalid(form)

class UserLogout(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('login')

class UserRegister(CreateView):
    form_class = ContractorRegisterForm
    template_name = "supply_chain/register.html"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        user = form.save()

        Contractor.objects.create(
            user=user,
            name=form.cleaned_data["name"],
            contact=form.cleaned_data["contact"],
            contact_email=form.cleaned_data["contact_email"],
            experience=form.cleaned_data["experience"],
            role=form.cleaned_data["role"],
            slug=slugify(form.cleaned_data["name"]),
        )
        return super().form_valid(form)

class CouncilDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'supply_chain/council_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        council = Council.objects.filter(user=self.request.user).first()
        if not council:
            raise PermissionDenied("You are not a council user")

        total_projects = Project.objects.filter(council=council).count()
        total_bids = Bid.objects.filter(council=council).count()
        pending_bids = Bid.objects.filter(
            council=council,
            status='pending'
        ).count()

        recent_projects = Project.objects.filter(council=council).order_by('-created_at')[:5]

        context.update({
            'council': council,
            'total_projects': total_projects,
            'total_bids': total_bids,
            'pending_bids': pending_bids,
            'projects': recent_projects,
        })

        return context

class ContractorDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'supply_chain/contractor_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        contractor = get_object_or_404(Contractor, user=self.request.user)

        all_bids = Bid.objects.filter(contractor=contractor)

        total_bids = all_bids.count()
        pending_bids = all_bids.filter(status='pending').count()
        awarded_projects = all_bids.filter(status='approved').count()
        rejected_bids = all_bids.filter(status='rejected').count()

        recent_bids = all_bids.select_related(
            'project', 'package', 'council'
        ).order_by('-created_at')[:5]

        context.update({
            'contractor': contractor,
            'total_bids': total_bids,
            'pending_bids': pending_bids,
            'awarded_projects': awarded_projects,
            'rejected_bids': rejected_bids,
            'recent_bids': recent_bids,
        })

        return context

@login_required
def project_list(request):
    if not hasattr(request.user, 'council'):
        return redirect('index')

    council = request.user.council
    search_query = request.GET.get('search', '')
    projects = Project.objects.all().annotate(
        package_count=Count('package'),
        total_bids=Count('package__bids'),
        approved_bids=Count('package__bids', filter=Q(package__bids__status='approved'))
    ).select_related('council').order_by('-created_at')

    if search_query:
        projects = projects.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    projects_with_ownership = []
    for project in projects:
        project.is_owner = project.council == council
        projects_with_ownership.append(project)

    paginator = Paginator(projects_with_ownership, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'projects': projects_with_ownership,
        'search_query': search_query,
        'page_obj': page_obj,
    }
    return render(request, 'supply_chain/project_list.html', context)

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if hasattr(request.user, 'council'):
        is_owner = project.council == request.user.council
        is_council = True
        is_contractor = False
    elif hasattr(request.user, 'contractor'):
        is_owner = False
        is_council = False
        is_contractor = True
    else:
        return redirect('index')

    packages = Package.objects.filter(project=project).annotate(
        bid_count=Count('bids'),
        lowest_bid=Min('bids__amount'),
        approved_bid_amount=Sum('bids__amount', filter=Q(bids__status='approved'))
    ).prefetch_related('bids__contractor')

    for package in packages:
        package.has_approved_bid = package.bids.filter(status='approved').exists()

    is_expired = project.is_expired()
    days_remaining = (project.end_date - timezone.now().date()).days
    can_end_project, end_message = project.can_be_ended() if is_owner else (False, "")
    pending_bids_count = project.bids.filter(status='pending').count() if is_owner else 0

    context = {
        'project': project,
        'packages': packages,
        'is_owner': is_owner,
        'is_council': is_council,
        'is_contractor': is_contractor,
        'is_expired': is_expired,
        'days_remaining': days_remaining,
        'can_end_project': can_end_project,
        'end_message': end_message,
        'pending_bids_count': pending_bids_count,
    }

    return render(request, 'supply_chain/project_detail.html', context)

@login_required
def open_projects(request):
    if not hasattr(request.user, 'contractor'):
        return redirect('index')

    contractor = request.user.contractor
    search_query = request.GET.get('search', '')
    max_budget = request.GET.get('max_budget', '')
    # projects = Project.objects.all().order_by('-created_at')
    projects = Project.objects.annotate(
        package_count=Count('package'),
        available_packages=Count(
            'package',
            filter=~Q(package__bids__status='approved')
        )
    ).order_by('-created_at')

    if search_query:
        projects = projects.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if max_budget:
        try:
            projects = projects.filter(budget__lte=int(max_budget))
        except ValueError:
            pass

    contractor_bids = Bid.objects.filter(contractor=contractor).values_list('package__project_id', flat=True)

    paginator = Paginator(projects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'projects': projects,
        'contractor_bids': list(contractor_bids),
        'search_query': search_query,
        'max_budget': max_budget,
        'page_obj': page_obj,
    }

    return render(request, 'supply_chain/open_projects.html', context)

class ProjectCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'supply_chain/project_create.html'

    def test_func(self):
        return hasattr(self.request.user, 'council')

    def handle_no_permission(self):
        messages.error(self.request, 'Only councils can create projects.')
        return redirect('index')

    def form_valid(self, form):
        form.instance.council = self.request.user.council
        response = super().form_valid(form)
        Activity.objects.create(
            user=self.request.user,
            activity_type='project_created',
            message=f'You created new project "{form.instance.title}"',
            project=form.instance
        )
        messages.success(self.request, f'Project "{form.instance.title}" created successfully!')
        return response

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'project_id': self.object.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = datetime.date.today().strftime('%Y-%m-%d')
        return context

@login_required
def project_delete(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if not hasattr(request.user, 'council'):
        messages.error(request, "You don't have permission to delete projects.")
        return redirect('index')

    if project.council != request.user.council:
        messages.error(request, "You don't have permission to delete this project.")
        return redirect('view_projects')

    project_title = project.title
    project.delete()

    Activity.objects.create(
        user=request.user,
        activity_type='project_deleted',
        message=f'You deleted project "{project_title}"',
    )

    messages.success(request, f'Project "{project_title}" has been deleted successfully.')
    return redirect('project_list')


@login_required
def project_end(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    if not hasattr(request.user, 'council'):
        messages.error(request, "You don't have permission to end projects.")
        return redirect('index')

    if project.council != request.user.council:
        messages.error(request, "You don't have permission to end this project.")
        return redirect('project_list')

    can_end, message = project.can_be_ended()

    if not can_end:
        messages.error(request, message)
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        project.status = 'completed'
        project.save()
        Activity.objects.create(
            user=request.user,
            activity_type='project_ended',
            message=f'You marked project "{project.title}" as completed',
            project=project
        )

        messages.success(request, f'Project "{project.title}" has been marked as completed.')
        return redirect('project_detail', project_id=project.id)

    return redirect('project_detail', project_id=project.id)

class PackageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a package - Only accessible by the project owner (council)"""
    model = Package
    form_class = PackageForm  # Use custom form instead of fields
    template_name = 'supply_chain/package_add.html'

    def test_func(self):
        return hasattr(self.request.user, 'council')

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(Project, id=self.kwargs['project_id'])

        # Check if council owns this project
        if hasattr(request.user, 'council') and self.project.council != request.user.council:
            messages.error(request, 'You can only add packages to your own projects.')
            return redirect('project_list')

        if self.project.is_expired():
            if self.project.status == 'completed':
                messages.error(request, 'Cannot add packages. This project has been marked as completed.')
            elif self.project.status == 'expired':
                messages.error(request, 'Cannot add packages. This project has expired.')
            else:
                messages.error(
                    request,
                    f'Cannot add packages to this project. The project ended on {self.project.end_date.strftime("%B %d, %Y")}.'
                )
            return redirect('project_detail', project_id=self.project.id)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['project'] = self.project

        # Calculate allocated budget from existing packages
        allocated = Package.objects.filter(
            project=self.project
        ).aggregate(
            total=Sum('budget')
        )['total'] or 0

        context['allocated_budget'] = allocated
        context['remaining_budget'] = self.project.budget - allocated
        context['allocated_packages_count'] = self.project.package_set.count()

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.project
        return kwargs

    def form_valid(self, form):
        form.instance.project = self.project
        response = super().form_valid(form)
        Activity.objects.create(
            user=self.request.user,
            activity_type='package_created',
            message=f'You added new package "{form.instance.title}" in project "{self.project.title}"',
            project=self.project,
            package=form.instance
        )
        messages.success(self.request, f'Package "{form.instance.title}" has been added successfully!')
        return response

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'project_id': self.project.id})

    def handle_no_permission(self):
        messages.error(self.request, 'Only council members can add packages.')
        return redirect('index')

class ContractorProjectDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View project detail and packages for contractor"""
    model = Project
    template_name = 'supply_chain/project_view_contractor.html'
    context_object_name = 'project'
    pk_url_kwarg = 'project_id'

    def test_func(self):
        return hasattr(self.request.user, 'contractor')

    def handle_no_permission(self):
        return redirect('index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contractor = self.request.user.contractor
        project = self.object

        packages = Package.objects.filter(project=project).annotate(
            bid_count=Count('bids'),
            lowest_bid=Min('bids__amount'),
        ).prefetch_related('bids__contractor')

        contractor_package_bids = Bid.objects.filter(
            contractor=contractor,
            project=project
        ).values_list('package_id', flat=True)

        for package in packages:
            package.contractor_has_bid = package.id in contractor_package_bids
            package.contractor_bid = None

            if package.contractor_has_bid:
                package.contractor_bid = package.bids.filter(
                    contractor=contractor
                ).first()

        context['packages'] = packages
        context['contractor'] = contractor
        context['contractor_package_bids'] = list(contractor_package_bids)

        return context

class PackageDetailView(LoginRequiredMixin, DetailView):
    model = Package
    template_name = 'supply_chain/package_detail.html'
    context_object_name = 'package'
    pk_url_kwarg = 'package_id'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()

        if not hasattr(request.user, 'council') and not hasattr(request.user, 'contractor'):
            messages.error(request, "You don't have permission to view packages.")
            return redirect('index')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = self.object
        user = self.request.user

        context['project'] = package.project

        if hasattr(user, 'council'):
            context['is_council'] = True
            context['is_owner'] = package.project.council == user.council

            bids = package.bids.select_related(
                'contractor',
                'contractor__user'
            ).order_by('amount')

            context['bids'] = bids
            context['total_bids'] = bids.count()
            context['pending_bids'] = bids.filter(status='pending').count()
            context['approved_bids'] = bids.filter(status='approved').count()
            context['rejected_bids'] = bids.filter(status='rejected').count()
            context['has_approved_bid'] = bids.filter(status='approved').exists()

        elif hasattr(user, 'contractor'):
            context['is_contractor'] = True

            my_bid = package.bids.filter(contractor=user.contractor).first()
            context['my_bid'] = my_bid

            can_submit = my_bid is None or my_bid.status == 'rejected'
            context['can_submit_bid'] = can_submit

            has_approved_bid = package.bids.filter(status='approved').exists()
            context['package_closed'] = has_approved_bid

        return context


class PackageDeleteView(LoginRequiredMixin, View):
    """Delete a package - Council only"""

    def get(self, request, package_id):
        package = get_object_or_404(Package, id=package_id)
        return redirect('project_detail', project_id=package.project.id)

    def post(self, request, package_id):
        package = get_object_or_404(Package, id=package_id)

        if not (hasattr(request.user, 'council') and
                package.project.council == request.user.council):
            messages.error(request, 'You do not have permission to delete this package.')
            return redirect('project_list')

        if package.has_approved_bid():
            messages.error(request, 'Cannot delete package with approved bid.')
            return redirect('project_detail', project_id=package.project.id)

        project_id = package.project.id
        project_title=package.project.title
        package_title = package.title
        package.delete()

        Activity.objects.create(
            user=request.user,
            activity_type='package_deleted',
            message=f'You deleted package "{package_title}" from project "{project_title}"',
            project=package.project
        )

        messages.success(request, f'Package "{package_title}" has been deleted successfully.')
        return redirect('project_detail', project_id=project_id)


class BidCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Bid
    form_class = BidForm
    template_name = 'supply_chain/bid_create.html'

    def test_func(self):
        return hasattr(self.request.user, 'contractor')

    def dispatch(self, request, *args, **kwargs):
        self.package = get_object_or_404(Package, id=self.kwargs['package_id'])
        self.project = self.package.project
        self.contractor = request.user.contractor

        if self.project.is_expired():
            if self.project.status == 'completed':
                messages.error(request, 'Cannot place bid. This project has been marked as completed.')
            elif self.project.status == 'expired':
                messages.error(request, 'Cannot place bid. This project has expired.')
            else:
                messages.error(
                    request,
                    f'Cannot place bid. This project ended on {self.project.end_date.strftime("%B %d, %Y")}.'
                )
            return redirect('package_detail', package_id=self.package.id)

        if self.package.has_approved_bid():
            messages.error(request, 'This package already has an approved bid. Bidding is closed.')
            return redirect('package_detail', package_id=self.package.id)

        existing_bid = Bid.objects.filter(
            contractor=self.contractor,
            package=self.package
        ).first()

        if existing_bid:
            messages.warning(request, 'You have already submitted a bid for this package.')
            return redirect('package_detail', package_id=self.package.id)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['package'] = self.package
        context['project'] = self.project
        # REMOVED: bid_count, lowest_bid - contractors shouldn't see other bids
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['package'] = self.package
        return kwargs

    def form_valid(self, form):
        bid = form.save(commit=False)
        bid.contractor = self.contractor
        bid.package = self.package
        bid.project = self.project
        bid.council = self.project.council
        bid.status = 'pending'

        if self.request.FILES:
            if 'document1' in self.request.FILES:
                bid.document1 = self.request.FILES['document1']
            if 'document2' in self.request.FILES:
                bid.document2 = self.request.FILES['document2']
            if 'document3' in self.request.FILES:
                bid.document3 = self.request.FILES['document3']

        bid.save()

        Activity.objects.create(
            user=self.request.user,
            activity_type='bid_placed',
            message=f'You placed a bid of £ {bid.amount:,.2f} for package "{self.package.title}" in project "{self.project.title}"',
            project=self.project,
            package=self.package,
            bid=bid
        )
        messages.success(
            self.request,
            f'Your bid of £ {bid.amount:,.2f} has been submitted successfully!'
        )
        return redirect('package_detail', package_id=self.package.id)

    def get_success_url(self):
        return reverse_lazy('package_detail', kwargs={'package_id': self.package.id})

    def handle_no_permission(self):
        messages.error(self.request, 'Only contractors can place bids.')
        return redirect('index')

class BidApproveView(LoginRequiredMixin, View):
    """Approve a bid - Council only"""

    def post(self, request, bid_id):
        bid = get_object_or_404(Bid, id=bid_id)
        package = bid.package

        if not (hasattr(request.user, 'council') and
                package.project.council == request.user.council):
            messages.error(request, 'You do not have permission to approve this bid.')
            return redirect('package_detail', package_id=package.id)

        if bid.status != 'pending':
            messages.warning(request, 'This bid has already been processed.')
            return redirect('package_detail', package_id=package.id)

        if package.bids.filter(status='approved').exists():
            messages.error(request, 'This package already has an approved bid.')
            return redirect('package_detail', package_id=package.id)

        bid.status = 'approved'
        bid.save()

        other_pending_bids = package.bids.filter(status='pending').exclude(id=bid.id)
        rejected_count = other_pending_bids.update(status='rejected')

        Activity.objects.create(
            user=request.user,
            activity_type='bid_approved',
            message=f'You approved bid from "{bid.contractor.name}" for package "{package.title}" in project "{package.project.title}"',
            project=package.project,
            package=package,
            bid=bid
        )

        Activity.objects.create(
            user=bid.contractor.user,
            activity_type='bid_approved',
            message=f'Your bid of £ {bid.amount:,.2f} for package "{package.title}" in project "{package.project.title}" was approved!',
            project=package.project,
            package=package,
            bid=bid
        )

        messages.success(
            request,
            f'Bid from {bid.contractor.name} has been approved! '
            f'{rejected_count} other bid(s) were automatically rejected.'
        )
        return redirect('package_detail', package_id=package.id)


class BidRejectView(LoginRequiredMixin, View):
    """Reject a bid - Council only"""

    def post(self, request, bid_id):
        bid = get_object_or_404(Bid, id=bid_id)
        package = bid.package

        if not (hasattr(request.user, 'council') and
                package.project.council == request.user.council):
            messages.error(request, 'You do not have permission to reject this bid.')
            return redirect('package_detail', package_id=package.id)

        if bid.status != 'pending':
            messages.warning(request, 'This bid has already been processed.')
            return redirect('package_detail', package_id=package.id)

        bid.status = 'rejected'
        bid.save()

        Activity.objects.create(
            user=request.user,
            activity_type='bid_rejected',
            message=f'You rejected bid from "{bid.contractor.name}" for package "{package.title}" in project "{package.project.title}"',
            project=package.project,
            package=package,
            bid=bid
        )

        Activity.objects.create(
            user=bid.contractor.user,
            activity_type='bid_rejected',
            message=f'Your bid of £ {bid.amount:,.2f} for package "{package.title}" in project "{package.project.title}" was rejected',
            project=package.project,
            package=package,
            bid=bid
        )

        messages.success(request, f'Bid from {bid.contractor.name} has been rejected.')
        return redirect('package_detail', package_id=package.id)

@login_required
def contractor_my_bids(request):
    if not hasattr(request.user, 'contractor'):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('index')

    contractor = request.user.contractor

    bids = Bid.objects.filter(contractor=contractor).select_related(
        'package',
        'package__project',
        'package__project__council'
    ).order_by('-date')

    total_bids = bids.count()
    pending_bids = bids.filter(status='pending').count()
    approved_bids = bids.filter(status='approved').count()
    rejected_bids = bids.filter(status='rejected').count()

    paginator = Paginator(bids, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'bids': bids,
        'total_bids': total_bids,
        'pending_bids': pending_bids,
        'approved_bids': approved_bids,
        'rejected_bids': rejected_bids,
        'page_obj': page_obj,
    }

    return render(request, 'supply_chain/contractor_my_bids.html', context)

@login_required
def council_all_bids(request):
    if not hasattr(request.user, 'council'):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('index')

    council = request.user.council

    bids = Bid.objects.filter(
        package__project__council=council
    ).select_related(
        'contractor',
        'contractor__user',
        'package',
        'package__project'
    ).order_by('-date')

    total_bids = bids.count()
    pending_bids = bids.filter(status='pending').count()
    approved_bids = bids.filter(status='approved').count()
    rejected_bids = bids.filter(status='rejected').count()

    paginator = Paginator(bids, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'bids': bids,
        'total_bids': total_bids,
        'pending_bids': pending_bids,
        'approved_bids': approved_bids,
        'rejected_bids': rejected_bids,
        'page_obj': page_obj,
    }

    return render(request, 'supply_chain/council_all_bids.html', context)

class TeamListView(LoginRequiredMixin, ListView):
    """View all teams - filtered by user role"""
    model = Team
    template_name = 'supply_chain/team_list.html'
    context_object_name = 'teams'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'council') and not hasattr(request.user, 'contractor'):
            messages.error(request, "You don't have permission to view teams.")
            return redirect('index')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user

        if hasattr(user, 'council'):
            return Team.objects.filter(
                project__council=user.council
            ).select_related('project').order_by('-created_at')

        elif hasattr(user, 'contractor'):
            return Team.objects.filter(
                project__package__bids__contractor=user.contractor,
                project__package__bids__status='approved'
            ).distinct().select_related('project').order_by('-created_at')

        return Team.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['is_council'] = hasattr(user, 'council')
        context['is_contractor'] = hasattr(user, 'contractor')

        teams_with_data = []
        for team in context['teams']:
            team.member_count_value = team.member_count()
            team.contractor_count_value = team.contractor_count()
            teams_with_data.append(team)

        context['teams'] = teams_with_data

        return context


class TeamDetailView(LoginRequiredMixin, DetailView):
    """View detailed information about a specific team"""
    model = Team
    template_name = 'supply_chain/team_detail.html'
    context_object_name = 'team'
    pk_url_kwarg = 'project_id'

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'council') and not hasattr(request.user, 'contractor'):
            messages.error(request, "You don't have permission to view teams.")
            return redirect('index')

        self.object = self.get_object()
        project = self.object.project
        user = request.user

        # Check permissions
        if hasattr(user, 'council'):
            if project.council != user.council:
                messages.error(request, "You don't have permission to view this team.")
                return redirect('team_list')

        elif hasattr(user, 'contractor'):
            is_member = Bid.objects.filter(
                package__project=project,
                contractor=user.contractor,
                status='approved'
            ).exists()

            if not is_member:
                messages.error(request, "You are not a member of this team.")
                return redirect('team_list')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object
        project = team.project
        user = self.request.user
        context['is_council'] = hasattr(user, 'council')
        context['is_contractor'] = hasattr(user, 'contractor')
        context['project'] = project

        if hasattr(user, 'contractor'):
            context['is_member'] = Bid.objects.filter(
                package__project=project,
                contractor=user.contractor,
                status='approved'
            ).exists()
        else:
            context['is_member'] = False

        members = team.get_members()
        context['members'] = members
        context['member_count'] = members.count()

        contractors = team.get_contractors()
        context['contractors'] = contractors
        context['contractor_count'] = contractors.count()

        return context

class ProfileView(LoginRequiredMixin, TemplateView):
    """Display user profile based on their role"""
    template_name = 'supply_chain/profile_view.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['user'] = user

        # Check if user is a council
        if hasattr(user, 'council'):
            context['profile'] = user.council
            context['user_type'] = 'Council'
            context['profile_fields'] = [
                {'label': 'Council Name', 'value': user.council.name},
                {'label': 'Contact Number', 'value': user.council.contact},
                {'label': 'Contact Email', 'value': user.council.contact_email},
                {'label': 'Member Since', 'value': user.council.created_at.strftime('%B %d, %Y')},
            ]

        # Check if user is a contractor
        elif hasattr(user, 'contractor'):
            context['profile'] = user.contractor
            context['user_type'] = 'Contractor'
            context['profile_fields'] = [
                {'label': 'Contractor Name', 'value': user.contractor.name},
                {'label': 'Contact Number', 'value': user.contractor.contact},
                {'label': 'Contact Email', 'value': user.contractor.contact_email},
                {'label': 'Experience', 'value': f"{user.contractor.experience} years"},
                {'label': 'Role/Specialization', 'value': user.contractor.role},
                {'label': 'Member Since', 'value': user.contractor.created_at.strftime('%B %d, %Y')},
            ]

        else:
            context['user_type'] = 'User'
            context['profile'] = None
            context['profile_fields'] = []

        return context

class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Edit user profile based on their role"""
    template_name = 'supply_chain/profile_edit.html'
    success_url = reverse_lazy('profile_view')
    login_url = 'login'

    def get_object(self, queryset=None):
        user = self.request.user

        if hasattr(user, 'council'):
            return user.council
        elif hasattr(user, 'contractor'):
            return user.contractor
        else:
            messages.error(self.request, 'Profile not found.')
            return redirect('profile_view')

    def get_form_class(self):
        user = self.request.user

        if hasattr(user, 'council'):
            return CouncilProfileForm
        elif hasattr(user, 'contractor'):
            return ContractorProfileForm
        else:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if hasattr(user, 'council'):
            context['user_type'] = 'Council'
            context['profile'] = user.council
        elif hasattr(user, 'contractor'):
            context['user_type'] = 'Contractor'
            context['profile'] = user.contractor

        return context

    @transaction.atomic
    def form_valid(self, form):
        profile = form.save(commit=False)

        user = self.request.user
        if 'username' in self.request.POST:
            user.username = self.request.POST['username']
        if 'email' in self.request.POST:
            user.email = self.request.POST['email']
        if 'first_name' in self.request.POST:
            user.first_name = self.request.POST['first_name']
        if 'last_name' in self.request.POST:
            user.last_name = self.request.POST['last_name']

        user.save()
        profile.save()

        Activity.objects.create(
            user=self.request.user,
            activity_type='profile_updated',
            message='You updated your profile information'
        )

        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Handle password change with custom form and success handling"""
    form_class = CustomPasswordChangeForm
    template_name = 'supply_chain/password_change.html'
    success_url = reverse_lazy('profile_view')
    login_url = 'login'

    def form_valid(self, form):
        response = super().form_valid(form)
        update_session_auth_hash(self.request, form.user)

        Activity.objects.create(
            user=self.request.user,
            activity_type='password_changed',
            message='You changed your password'
        )

        messages.success(self.request, 'Your password has been changed successfully!')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

@login_required
def council_reports(request):
    """Main reports page with overall summary and project list"""
    if not hasattr(request.user, 'council'):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('index')

    council = request.user.council

    # Overall Statistics
    total_projects = Project.objects.filter(council=council).count()
    total_packages = Package.objects.filter(project__council=council).count()
    total_bids_received = Bid.objects.filter(council=council).count()

    total_budget = Project.objects.filter(council=council).aggregate(
        total=Sum('budget')
    )['total'] or 0

    allocated_budget = Package.objects.filter(
        project__council=council
    ).aggregate(total=Sum('budget'))['total'] or 0

    awarded_budget = Bid.objects.filter(
        council=council,
        status='approved'
    ).aggregate(total=Sum('amount'))['total'] or 0

    pending_bids = Bid.objects.filter(council=council, status='pending').count()
    approved_bids = Bid.objects.filter(council=council, status='approved').count()
    rejected_bids = Bid.objects.filter(council=council, status='rejected').count()

    # Project-wise data for charts
    projects = Project.objects.filter(council=council).annotate(
        package_count=Count('package'),
        bid_count=Count('package__bids'),
        approved_bid_count=Count('package__bids', filter=Q(package__bids__status='approved')),
        total_awarded=Sum('package__bids__amount', filter=Q(package__bids__status='approved'))
    ).order_by('-created_at')

    paginator = Paginator(projects, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    project_names = [p.title[:20] + '...' if len(p.title) > 20 else p.title for p in projects]
    project_budgets = [float(p.budget) for p in projects]
    project_packages = [p.package_count for p in projects]
    project_bids = [p.bid_count for p in projects]

    context = {
        'council': council,
        'total_projects': total_projects,
        'total_packages': total_packages,
        'total_bids_received': total_bids_received,
        'total_budget': total_budget,
        'allocated_budget': allocated_budget,
        'awarded_budget': awarded_budget,
        'pending_bids': pending_bids,
        'approved_bids': approved_bids,
        'rejected_bids': rejected_bids,
        'projects': projects,
        'page_obj': page_obj,
        'project_names': project_names,
        'project_budgets': project_budgets,
        'project_packages': project_packages,
        'project_bids': project_bids,
    }

    return render(request, 'supply_chain/council_reports.html', context)

@login_required
def download_project_report(request, project_id):
    if not hasattr(request.user, 'council'):
        messages.error(request, "You don't have permission to download reports.")
        return redirect('index')

    project = get_object_or_404(Project, id=project_id)

    if project.council != request.user.council:
        messages.error(request, "You don't have permission to download this report.")
        return redirect('council_reports')

    Activity.objects.create(
        user=request.user,
        activity_type='report_downloaded',
        message=f'You downloaded report for project "{project.title}"',
        project=project
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.HexColor('#1A1F2E'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1A1F2E'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#1A1F2E'),
        fontName='Helvetica'
    )

    elements.append(Paragraph(f"Project Report: {project.title}", title_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Project Information", heading_style))

    project_info = [
        ['Field', 'Value'],
        ['Project Title', project.title],
        ['Council', project.council.name],
        ['Budget', f'£ {project.budget:,.2f}'],
        ['Start Date', project.start_date.strftime('%B %d, %Y')],
        ['End Date', project.end_date.strftime('%B %d, %Y')],
        ['Created On', project.created_at.strftime('%B %d, %Y')],
        ['Status', 'Active' if project.end_date >= project.created_at.date() else 'Expired'],
    ]

    project_table = Table(project_info, colWidths=[2 * inch, 4 * inch])
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00BF62')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1A1F2E')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
    ]))

    elements.append(project_table)
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph("Project Description", heading_style))
    elements.append(Paragraph(project.description, normal_style))
    elements.append(Spacer(1, 0.3 * inch))

    packages = Package.objects.filter(project=project).annotate(
        bid_count=Count('bids'),
        approved_bid_count=Count('bids', filter=Q(bids__status='approved'))
    )

    elements.append(Paragraph(f"Packages ({packages.count()})", heading_style))

    if packages.exists():
        package_data = [['Package Title', 'Budget', 'Bids', 'Status']]

        for pkg in packages:
            status = 'Awarded' if pkg.approved_bid_count > 0 else 'Open'
            package_data.append([
                pkg.title[:30],
                f'£ {pkg.budget:,.2f}',
                str(pkg.bid_count),
                status
            ])

        package_table = Table(package_data, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch, 1 * inch])
        package_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00BF62')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1A1F2E')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
        ]))

        elements.append(package_table)
    else:
        elements.append(Paragraph("No packages created yet.", normal_style))

    elements.append(Spacer(1, 0.3 * inch))
    bids = Bid.objects.filter(project=project).select_related('contractor', 'package').order_by('package', 'amount')
    elements.append(Paragraph(f"Bids Received ({bids.count()})", heading_style))

    if bids.exists():
        bid_data = [['Package', 'Contractor', 'Amount', 'Status']]

        for bid in bids:
            bid_data.append([
                bid.package.title[:25],
                bid.contractor.name[:25],
                f'£ {bid.amount:,.2f}',
                bid.status.capitalize()
            ])

        bid_table = Table(bid_data, colWidths=[2 * inch, 2 * inch, 1.5 * inch, 1 * inch])
        bid_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00BF62')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1A1F2E')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
        ]))

        elements.append(bid_table)
    else:
        elements.append(Paragraph("No bids received yet.", normal_style))

    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("Summary", heading_style))

    total_awarded = bids.filter(status='approved').aggregate(total=Sum('amount'))['total'] or 0

    summary_data = [
        ['Metric', 'Value'],
        ['Total Packages', str(packages.count())],
        ['Total Bids Received', str(bids.count())],
        ['Pending Bids', str(bids.filter(status='pending').count())],
        ['Approved Bids', str(bids.filter(status='approved').count())],
        ['Rejected Bids', str(bids.filter(status='rejected').count())],
        ['Total Budget', f'£ {project.budget:,.2f}'],
        ['Total Awarded', f'£ {total_awarded:,.2f}'],
        ['Remaining Budget', f'£ {project.budget - total_awarded:,.2f}'],
    ]

    summary_table = Table(summary_data, colWidths=[2.5 * inch, 3.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00BF62')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1A1F2E')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
    ]))
    elements.append(summary_table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="project_report_{project.id}_{project.title[:30]}.pdf"'
    response.write(pdf)

    return response

@login_required
def my_activity(request):
    activities = Activity.objects.filter(user=request.user).order_by('-created_at')[:50]

    Activity.objects.filter(user=request.user, is_read=False).update(is_read=True)
    paginator = Paginator(activities, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'activities': activities,
        'page_obj': page_obj,
    }

    return render(request, 'supply_chain/my_activity.html', context)