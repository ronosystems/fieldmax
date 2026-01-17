from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_http_methods
from django.db import transaction
from rest_framework import viewsets
import json
from decimal import Decimal, InvalidOperation
import traceback
from django.core.exceptions import ValidationError
from django.contrib import messages
from .models import Category, Product, StockEntry
from .serializers import CategorySerializer, ProductSerializer, StockEntrySerializer
from .forms import CategoryForm, ProductForm, StockEntryForm, ProductFormSet
import logging
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET




logger = logging.getLogger(__name__)




# ====================================
#  CATEG0RY VIEW SET
# ====================================

class CategoryViewSet(viewsets.ModelViewSet):
    """API endpoint for categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer






# ====================================
# GET CATEGORIES (AJAX)
# ====================================

@login_required
@require_http_methods(["GET"])
def get_categories(request):
    """Get all categories for dropdowns (AJAX)"""
    try:
        categories = Category.objects.filter(is_active=True).values(
            'id', 'name', 'category_code', 'item_type'
        ).order_by('name')
        
        return JsonResponse({
            "success": True,
            "categories": list(categories)
        })
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e),
            "categories": []
        }, status=500)



# ====================================
# GET CATEGORIES API
# ====================================

@login_required
@require_GET
def get_categories_api(request):
    """API endpoint to get all categories"""
    try:
        # Get all categories (no is_active field, so get all)
        categories = Category.objects.all().order_by('name')
        
        data = []
        for cat in categories:
            # Count products for this category
            product_count = Product.objects.filter(category=cat, is_active=True).count()
            
            category_data = {
                'id': cat.id,
                'name': cat.name,
                'code': cat.category_code or '',
                'item_type': cat.get_item_type_display() if hasattr(cat, 'get_item_type_display') else cat.item_type,
                'sku_type': cat.get_sku_type_display() if hasattr(cat, 'get_sku_type_display') else cat.sku_type,
                'product_count': product_count,
            }
            data.append(category_data)
        
        return JsonResponse({'success': True, 'categories': data})
        
    except Exception as e:
        logger.error(f"Error in get_categories_api: {e}", exc_info=True)
        return JsonResponse(
            {'success': False, 'message': str(e), 'categories': []},
            status=500
        )



# ====================================
# PRODUCT VIEW SET
# ====================================

class ProductViewSet(viewsets.ModelViewSet):
    """API endpoint for products"""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    def get_queryset(self):
        """Filter products based on query parameters"""
        queryset = Product.objects.select_related('category', 'owner').all()
        
        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by status
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by item type (single/bulk)
        item_type = self.request.query_params.get('item_type', None)
        if item_type:
            queryset = queryset.filter(category__item_type=item_type)
        
        # Search by name or SKU
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(sku_value__icontains=search) |
                Q(product_code__icontains=search)
            )
        
        return queryset











# ====================================
#STOCK ENTRY VIEW SET
# ====================================

class StockEntryViewSet(viewsets.ModelViewSet):
    """API endpoint for stock entries"""
    queryset = StockEntry.objects.all()
    serializer_class = StockEntrySerializer
    
    def get_queryset(self):
        """Filter stock entries by product or date range"""
        queryset = StockEntry.objects.select_related('product', 'created_by').all()
        
        # Filter by product
        product_id = self.request.query_params.get('product', None)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by entry type
        entry_type = self.request.query_params.get('entry_type', None)
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        return queryset











# ====================================
# CATEGORY LIST VIEWS
# ====================================

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "inventory/category_list.html"
    context_object_name = "categories"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add product counts per category
        for category in context['categories']:
            category.product_count = category.products.filter(is_active=True).count()
        return context












# ====================================
# CATEGORY DETAIL VIEW
# ====================================

class CategoryDetailView(LoginRequiredMixin, DetailView):
    model = Category
    template_name = "inventory/category_detail.html"
    context_object_name = "category"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_object()
        
        # Get products in this category
        context['products'] = category.products.filter(is_active=True)
        context['total_products'] = context['products'].count()
        
        # Calculate inventory value safely
        total_value = Decimal('0.00')
        for p in context['products']:
            buying_price = p.buying_price or Decimal('0.00')
            quantity = p.quantity or 0
            total_value += buying_price * quantity
        
        context['inventory_value'] = total_value
        
        return context











# ====================================
# CATEGORY CREATE VIEW
# ====================================

class CategoryCreateView(LoginRequiredMixin, CreateView):
    """
    Create a category with inline products
    Handles both regular form submission and AJAX
    """
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("inventory:category-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Category'
        context['button_text'] = 'Create Category'
        
        # Add formset to context
        if self.request.POST:
            context['products'] = ProductFormSet(self.request.POST, instance=self.object)
        else:
            context['products'] = ProductFormSet(instance=self.object)
        
        # Add choices for dropdowns
        context['item_type_choices'] = Category.ITEM_TYPE_CHOICES
        context['sku_type_choices'] = Category.SKU_TYPE_CHOICES
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle both AJAX and normal POST"""
        self.object = None
        
        logger.info("=== CategoryCreateView POST ===")
        logger.info(f"POST data keys: {list(request.POST.keys())}")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        logger.info(f"Is AJAX: {is_ajax}")
        
        try:
            form = self.get_form()
            
            # Get the formset
            products_formset = ProductFormSet(request.POST)
            
            logger.info(f"Form valid: {form.is_valid()}")
            logger.info(f"Formset valid: {products_formset.is_valid()}")
            
            if form.errors:
                logger.error(f"Form errors: {form.errors}")
            if products_formset.errors:
                logger.error(f"Formset errors: {products_formset.errors}")
            
            if form.is_valid() and products_formset.is_valid():
                return self.form_valid(form, products_formset)
            else:
                return self.form_invalid(form, products_formset)
                
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"ERROR in POST: {str(e)}")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Server error: {str(e)}'
                }, status=500)
            raise

    def form_valid(self, form, products_formset):
        """Process valid form and formset"""
        logger.info("=== form_valid START ===")
        
        is_ajax = self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            with transaction.atomic():
                # Save the category
                self.object = form.save()
                logger.info(f"✅ Category saved: {self.object.name} ({self.object.category_code})")
                
                # Assign category to formset and save products
                products_formset.instance = self.object
                products = products_formset.save(commit=False)
                
                product_count = 0
                for form_obj, product in zip(products_formset.forms, products):
                    # ✅ Skip empty forms (no product entered)
                    if not form_obj.cleaned_data:
                       continue

                    # ✅ Skip rows where name & quantity are empty
                    if not product.name and not product.quantity:
                       continue

                    # Set default values
                    product.owner = self.request.user
                    
                    # Set quantity based on category type
                    if self.object.is_single_item:
                        product.quantity = 0
                    elif product.quantity is None:
                        product.quantity = 0
                    
                    # Set default prices if not provided
                    if not product.buying_price:
                        product.buying_price = 0
                    if not product.selling_price:
                        product.selling_price = 0
                    
                    product.save()
                    product_count += 1
                    logger.info(f"✅ Product saved: {product.name} ({product.product_code})")
                
                # Handle deletions
                for obj in products_formset.deleted_objects:
                    obj.delete()
                
                logger.info(f"✅ Total products created: {product_count}")
                
                # Return response
                if is_ajax:
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Category "{self.object.name}" created with {product_count} product(s)',
                        'category_id': self.object.pk,
                        'category_code': self.object.category_code,
                        'product_count': product_count
                    })
                else:
                    return redirect(self.success_url)
                    
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"ERROR in form_valid: {str(e)}")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error saving category: {str(e)}'
                }, status=400)
            
            form.add_error(None, str(e))
            return self.form_invalid(form, products_formset)

    def form_invalid(self, form, products_formset):
        """Handle invalid form/formset"""
        logger.error("=== form_invalid ===")
        logger.error(f"Form errors: {form.errors}")
        logger.error(f"Formset errors: {products_formset.errors}")
        
        is_ajax = self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax:
            # Collect all errors
            errors = {}
            
            if form.errors:
                errors['category'] = dict(form.errors)
            
            if products_formset.errors:
                errors['products'] = []
                for i, form_errors in enumerate(products_formset.errors):
                    if form_errors:
                        errors['products'].append({
                            'index': i,
                            'errors': dict(form_errors)
                        })
            
            # Get first error message
            error_message = "Validation error"
            if form.errors:
                first_field = list(form.errors.keys())[0]
                first_error = form.errors[first_field][0]
                error_message = f"{first_field}: {first_error}" if first_field != '__all__' else first_error
            elif products_formset.errors:
                for form_errors in products_formset.errors:
                    if form_errors:
                        first_field = list(form_errors.keys())[0]
                        first_error = form_errors[first_field][0]
                        error_message = f"Product {first_field}: {first_error}"
                        break
            
            return JsonResponse({
                'status': 'error',
                'message': error_message,
                'errors': errors
            }, status=400)
        
        # Normal form submission - re-render with errors
        context = self.get_context_data()
        context['form'] = form
        context['products'] = products_formset
        return self.render_to_response(context)









# ====================================
# CATEGORY UPDATE VIEW
# ====================================

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "inventory/category_form.html"
    success_url = reverse_lazy("category-list")











# ====================================
# CATEGORY DELETE VIEW
# ====================================

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = "inventory/category_confirm_delete.html"
    success_url = reverse_lazy("category-list")
    
    def post(self, request, *args, **kwargs):
        category = self.get_object()
        
        # Check if category has products
        if category.products.exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Cannot delete category. It has {category.products.count()} products.'
                }, status=400)
        
        return super().post(request, *args, **kwargs)














# ====================================
# PRODUCT LIST VIEWS
# ====================================

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = "inventory/product_list.html"
    context_object_name = "products"
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'owner').filter(is_active=True)
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(product_code__icontains=search) |
                Q(sku_value__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['total_products'] = self.get_queryset().count()
        return context











# ====================================
# PRODUCT DETAIL VIEW
# ====================================

class ProductDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        try:
            product = get_object_or_404(
                Product.objects.select_related('category', 'owner'),
                pk=pk
            )

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Safely handle None values
                buying_price = float(product.buying_price or 0)
                selling_price = float(product.selling_price or 0)
                profit_margin = float(product.profit_margin or 0)
                profit_percentage = float(product.profit_percentage or 0)

                owner_data = None
                if product.owner:
                    owner_data = {
                        'id': product.owner.id,
                        'username': product.owner.username
                    }

                return JsonResponse({
                    'status': 'success',
                    'product': {
                        'id': product.id,
                        'product_code': product.product_code,
                        'name': product.name,
                        'category': {
                            'id': product.category.id,
                            'name': product.category.name,
                            'item_type': product.category.item_type,
                            'sku_type': product.category.get_sku_type_display(),
                        },
                        'sku_value': product.sku_value,
                        'quantity': product.quantity or 0,
                        'buying_price': buying_price,
                        'selling_price': selling_price,
                        'status': product.get_status_display(),
                        'can_restock': getattr(product, 'can_restock', False),
                        'profit_margin': profit_margin,
                        'profit_percentage': profit_percentage,
                        'is_active': product.is_active,
                        'owner': owner_data,
                        'created_at': product.created_at.isoformat() if product.created_at else None,
                    }
                })

            # Normal HTML request
            context = {
                'product': product,
                'stock_entries': product.stock_entries.all()[:20],
                'total_stock_entries': product.stock_entries.count(),
            }
            return render(request, 'inventory/product_detail.html', context)

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=400)
            raise










# ====================================
# PRODUCT CREATE VIEW
# ====================================

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "inventory/product_form.html"
    success_url = reverse_lazy("inventory:product-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Product'
        context['button_text'] = 'Create Product'
        context['categories'] = Category.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        """Handle AJAX & normal POST"""
        self.object = None
        
        logger.info("=== ProductCreateView POST ===")
        logger.info(f"POST data: {request.POST}")
        logger.info(f"FILES data: {request.FILES}")
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        logger.info(f"Is AJAX: {is_ajax}")
        
        try:
            # ✅ CRITICAL: Pass request.FILES to the form
            form = self.get_form()
            logger.info("Form created successfully")

            if form.is_valid():
                logger.info("Form is valid")
                return self.form_valid(form)
            else:
                logger.error(f"Form invalid: {form.errors}")
                return self.form_invalid(form)

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"ERROR in POST: {str(e)}")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            if is_ajax:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
            raise

    def form_valid(self, form):
        logger.info("=== form_valid START ===")
        try:
            with transaction.atomic():
                category = form.cleaned_data.get('category')
                name = form.cleaned_data.get('name')
                sku_value = (form.cleaned_data.get('sku_value') or "").strip()
                barcode = (form.cleaned_data.get('barcode') or "").strip() 
                quantity = form.cleaned_data.get('quantity') or 1
                buying_price = form.cleaned_data.get('buying_price')
                selling_price = form.cleaned_data.get('selling_price')
                
                # ✅ Get the uploaded image
                image = form.cleaned_data.get('image')
                if image:
                    logger.info(f"Image uploaded: {image.name} ({image.size} bytes)")
                else:
                    logger.info("No image uploaded")

                # ===============================
                # SINGLE ITEM
                # ===============================
                if category.is_single_item:
                    if not sku_value:
                        raise ValidationError(f"{category.get_sku_type_display()} is required for single items")
                    if Product.objects.filter(sku_value__iexact=sku_value, is_active=True).exists():
                        raise ValidationError(f"{category.get_sku_type_display()} '{sku_value}' already exists")
                    
                    form.instance.owner = self.request.user
                    form.instance.quantity = 1
                    form.instance.image = image
                    form.instance.barcode = None                    
                    self.object = form.save()
                    
                    # Create stock entry
                    StockEntry.objects.create(
                        product=self.object,
                        quantity=1,
                        entry_type='purchase',
                        unit_price=buying_price,
                        total_amount=buying_price,
                        created_by=self.request.user,
                        notes="Initial single item stock entry"
                    )
                    logger.info(f"[SINGLE ITEM] Product created: {self.object.product_code}")
                    if self.object.image:
                        logger.info(f"[SINGLE ITEM] Image saved: {self.object.image.url}")

                # ===============================
                # BULK ITEM
                # ===============================
                else:
                    existing_product = Product.objects.filter(
                        name__iexact=name,
                        category=category,
                        is_active=True
                    ).first()

                    # ✅ If barcode provided, also check for duplicate barcode
                    if barcode and Product.objects.filter(barcode__iexact=barcode, is_active=True).exists():
                        existing_by_barcode = Product.objects.filter(barcode__iexact=barcode, is_active=True).first()
                        if existing_by_barcode and existing_by_barcode != existing_product:
                            raise ValidationError(f"Barcode '{barcode}' already exists for product: {existing_by_barcode.name}")
                                    
                    if existing_product:
                        self.object = existing_product
                        logger.info(f"[BULK ITEM] Found existing product: {existing_product.product_code}")
                        
                        # ✅ If new image uploaded, update the product image
                        if image and existing_product:
                            existing_product.image = image
                        if barcode:
                            existing_product.barcode = barcode
                        existing_product.save()
                        logger.info(f"[BULK ITEM] Updated image for existing product")
                    else:
                        # Create new product with quantity=0
                        form.instance.owner = self.request.user
                        form.instance.quantity = 0
                        
                        # ✅ Set the image on the instance
                        form.instance.image = image
                        form.instance.barcode = barcode
                        form.instance.sku_value = None

                        self.object = form.save()
                        logger.info(f"[BULK ITEM] Created new product: {self.object.product_code} with barcode: {barcode}")
                        if self.object.image:
                            logger.info(f"[BULK ITEM] Image saved: {self.object.image.url}")

                    # Create stock entry to add quantity
                    StockEntry.objects.create(
                        product=self.object,
                        quantity=quantity,
                        entry_type='purchase',
                        unit_price=buying_price,
                        total_amount=buying_price * quantity,
                        created_by=self.request.user,
                        notes="Initial stock entry via ProductCreateView"
                    )
                    logger.info(f"[BULK ITEM] Stock entry created for {self.object.product_code}, Qty: {quantity}")

                # Return response with image URL
                image_url = None
                if self.object and self.object.image:
                    image_url = self.object.image.url
                
                # Return response
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        "success": True,
                        "message": f'Product "{self.object.name}" saved successfully!',
                        "product_id": self.object.pk,
                        "product_code": self.object.product_code,
                        "quantity": self.object.quantity,
                        "barcode": self.object.barcode,
                        "image_url": image_url  # ✅ Include image URL in response
                    })
                else:
                    return redirect(self.success_url)

        except ValidationError as ve:
            logger.error(f"ValidationError: {ve}")
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(ve)}, status=400)
            form.add_error(None, str(ve))
            return self.form_invalid(form)

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"ERROR: {str(e)}")
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)
            form.add_error(None, str(e))
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.error(f"Form invalid - Errors: {form.errors}")
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_message = "Validation error"
            if form.errors:
                for field, errors in form.errors.items():
                    if errors:
                        error_message = f"{field}: {errors[0]}" if field != '__all__' else errors[0]
                        break
            return JsonResponse({
                "success": False,
                "message": error_message,
                "errors": dict(form.errors)
            }, status=400)
        return super().form_invalid(form)



# ===========================================
# PRINT CODE LABELS VIEW
#============================================
@login_required
def print_labels_view(request):
    """
    Display the print labels preview page.
    Data is passed via sessionStorage from the main page.
    """
    return render(request, 'inventory/print_code.html')





# ===========================================
# PRODUCT RESTOCT VIEW
#============================================

class ProductRestockView(LoginRequiredMixin, TemplateView):
    """View for restocking products - search first, then restock"""
    template_name = "inventory/product_restock.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Restock Products'
        return context












# ===========================================
# SEARCH PRODUCT FOR RESTOCK
#============================================

@login_required
@require_http_methods(["GET"])
def search_product_for_restock(request):
    """Search for a product by name, code, or SKU"""
    search_term = request.GET.get('search', '').strip()
    
    if not search_term:
        return JsonResponse({
            'success': False,
            'message': 'Please enter a product name, code, or SKU'
        }, status=400)
    
    try:
        # Search in multiple fields
        products = Product.objects.filter(
            Q(name__icontains=search_term) |
            Q(product_code__icontains=search_term) |
            Q(sku_value__iexact=search_term),
            is_active=True
        ).select_related('category')
        
        if not products.exists():
            return JsonResponse({
                'success': False,
                'message': f'No product found matching "{search_term}"'
            }, status=404)
        
        # If multiple products found, return list
        if products.count() > 1:
            product_list = [{
                'id': p.id,
                'name': p.name,
                'product_code': p.product_code,
                'sku_value': p.sku_value or 'N/A',
                'category': p.category.name,
                'current_quantity': p.quantity,
                'buying_price': float(p.buying_price) if p.buying_price else 0,
                'selling_price': float(p.selling_price) if p.selling_price else 0,
                'is_single_item': p.category.is_single_item
            } for p in products[:10]]  # Limit to 10 results
            
            return JsonResponse({
                'success': True,
                'multiple': True,
                'products': product_list,
                'count': products.count()
            })
        
        # Single product found
        product = products.first()
        
        # Check if it's a single item
        if product.category.is_single_item:
            return JsonResponse({
                'success': False,
                'message': f'"{product.name}" is a single item and cannot be restocked. Each single item must be added individually.',
                'is_single_item': True
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'multiple': False,
            'product': {
                'id': product.id,
                'name': product.name,
                'product_code': product.product_code,
                'sku_value': product.sku_value or 'N/A',
                'category': product.category.name,
                'current_quantity': product.quantity,
                'buying_price': float(product.buying_price) if product.buying_price else 0,
                'selling_price': float(product.selling_price) if product.selling_price else 0,
                'is_single_item': product.category.is_single_item
            }
        })
    
    except Exception as e:
        logger.error(f"Search error: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Search error: {str(e)}'
        }, status=500)














# ===========================================
# PROCESS RESTOCK VIEW
#============================================

@login_required
@require_http_methods(["POST"])
def process_restock(request):
    """Process the restock operation"""
    try:
        product_id = request.POST.get('product_id')
        quantity = request.POST.get('quantity')
        buying_price = request.POST.get('buying_price')
        selling_price = request.POST.get('selling_price')
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        if not all([product_id, quantity, buying_price]):
            return JsonResponse({
                'success': False,
                'message': 'Product, quantity, and buying price are required'
            }, status=400)
        
        product = get_object_or_404(Product, pk=product_id, is_active=True)
        
        # Check if single item
        if product.category.is_single_item:
            return JsonResponse({
                'success': False,
                'message': 'Cannot restock single items'
            }, status=400)
        
        try:
            quantity = int(quantity)
            buying_price = float(buying_price)
            selling_price = float(selling_price) if selling_price else None
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid number format'
            }, status=400)
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Quantity must be greater than 0'
            }, status=400)
        
        if buying_price < 0:
            return JsonResponse({
                'success': False,
                'message': 'Buying price cannot be negative'
            }, status=400)
        
        # Create stock entry and update prices
        with transaction.atomic():
            # Create stock entry
            stock_entry = StockEntry.objects.create(
                product=product,
                quantity=quantity,
                entry_type='purchase',
                unit_price=buying_price,
                total_amount=buying_price * quantity,
                created_by=request.user,
                notes=notes or "Restock via search"
            )
            
            # Update product prices if provided
            if buying_price:
                product.buying_price = buying_price
            if selling_price and selling_price > 0:
                product.selling_price = selling_price
            product.save()
            
            logger.info(f"Restocked: {product.product_code} - Qty: {quantity}")
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully added {quantity} units to {product.name}',
            'product': {
                'id': product.id,
                'name': product.name,
                'product_code': product.product_code,
                'new_quantity': product.quantity,
                'buying_price': float(product.buying_price),
                'selling_price': float(product.selling_price)
            },
            'stock_entry_id': stock_entry.id
        })
    
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Product not found'
        }, status=404)
    
    except Exception as e:
        logger.error(f"Restock error: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)












# ===========================================
# PRODUCT EDIT VIEW
#============================================

class ProductEditView(LoginRequiredMixin, UpdateView):
    """Handle product editing"""
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product-list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Product'
        context['button_text'] = 'Update Product'
        context['categories'] = Category.objects.all()
        return context
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Track quantity changes
                old_product = Product.objects.get(pk=self.object.pk)
                old_quantity = old_product.quantity or 0
                new_quantity = form.cleaned_data.get('quantity', 0) or 0
                
                # ✅ FIX: Check if this is a single item
                is_single_item = self.object.category.is_single_item
                
                response = super().form_valid(form)
                
                # ✅ FIX: Only create adjustment entry for BULK items when quantity changes
                if not is_single_item and old_quantity != new_quantity:
                    quantity_diff = new_quantity - old_quantity
                    buying_price = self.object.buying_price or Decimal('0.00')
                    
                    StockEntry.objects.create(
                        product=self.object,
                        quantity=quantity_diff,
                        entry_type='adjustment',
                        unit_price=buying_price,
                        total_amount=abs(quantity_diff) * buying_price,
                        created_by=self.request.user,
                        notes=f"Manual adjustment: {old_quantity} → {new_quantity}"
                    )
                
                # ✅ FIX: For single items, log warning if quantity changed
                elif is_single_item and old_quantity != new_quantity:
                    logger.warning(
                        f"Quantity change attempted on single item {self.object.product_code}: "
                        f"{old_quantity} → {new_quantity}. No stock entry created."
                    )
                
                # AJAX response
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Product "{self.object.name}" updated successfully',
                        'product_id': self.object.pk
                    })
                
                return response
            
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}")
            logger.error(traceback.format_exc())
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error updating product: {str(e)}'
                }, status=400)
            raise
    
    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Validation error',
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)







# ===========================================
# PRODUCT UPDATE VIEW
#============================================

class ProductUpdateView(LoginRequiredMixin, View):
    """AJAX-only quick update for product fields"""
    
    def post(self, request, pk):
        try:
            with transaction.atomic():
                data = json.loads(request.body)
                product = get_object_or_404(Product, pk=pk)
                
                # Track old values
                old_quantity = product.quantity or 0
                
                # Update fields
                if 'name' in data:
                    product.name = data['name']
                    
                if 'buying_price' in data and data['buying_price'] not in [None, '']:
                    try:
                        product.buying_price = Decimal(str(data['buying_price']))
                    except (ValueError, InvalidOperation):
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Invalid buying price format'
                        }, status=400)
                
                if 'selling_price' in data and data['selling_price'] not in [None, '']:
                    try:
                        product.selling_price = Decimal(str(data['selling_price']))
                    except (ValueError, InvalidOperation):
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Invalid selling price format'
                        }, status=400)
                
                if 'quantity' in data:
                    try:
                        new_quantity = int(data['quantity'])
                    except (ValueError, TypeError):
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Invalid quantity format'
                        }, status=400)
                    
                    # Validate quantity change for single items
                    if hasattr(product.category, 'is_single_item') and product.category.is_single_item:
                        if new_quantity not in [0, 1]:
                            return JsonResponse({
                                'status': 'error',
                                'message': 'Single items can only have quantity 0 or 1'
                            }, status=400)
                    
                    product.quantity = new_quantity
                
                product.save()
                
                # Create adjustment entry if quantity changed
                if 'quantity' in data and old_quantity != product.quantity:
                    quantity_diff = product.quantity - old_quantity
                    buying_price = product.buying_price or Decimal('0.00')
                    
                    StockEntry.objects.create(
                        product=product,
                        quantity=quantity_diff,
                        entry_type='adjustment',
                        unit_price=buying_price,
                        total_amount=abs(quantity_diff) * buying_price,
                        created_by=request.user,
                        notes="Quick update adjustment"
                    )
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Product updated successfully'
                })
            
        except Exception as e:
            print("Error in quick update:")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error',
                'message': f'Error: {str(e)}'
            }, status=400)











# ===========================================
# PRODUCT DELETE VIEW
#============================================

class ProductDeleteView(LoginRequiredMixin, View):
    """Handle AJAX product deletion"""
    
    def post(self, request, pk):
        try:
            product = get_object_or_404(Product, pk=pk)
            product_name = product.name
            product_code = product.product_code
            
            # Soft delete (mark as inactive) instead of hard delete
            product.is_active = False
            product.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'Product "{product_name}" ({product_code}) deleted successfully'
            })
            
        except Product.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Product not found'
            }, status=404)
            
        except Exception as e:
            print("Error deleting product:")
            print(traceback.format_exc())
            return JsonResponse({
                'status': 'error',
                'message': f'Error deleting product: {str(e)}'
            }, status=400)
        









# ============================================
# GET TRANSFER USERS
# ============================================

@login_required
@require_http_methods(["GET"])
def get_transfer_users(request):
    """Get list of users for transfer dropdown"""
    try:
        users = User.objects.filter(is_active=True).exclude(id=request.user.id)
        user_list = [
            {
                'id': user.id,
                'username': user.username,
                'full_name': user.get_full_name() or user.username
            }
            for user in users
        ]
        
        return JsonResponse({
            'success': True,
            'users': user_list
        })
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error loading users'
        }, status=500)











# ===========================================
# PRODUCT TRANSFER SEARCH
#============================================

@login_required
@require_http_methods(["GET"])
def product_transfer_search(request):
    """Search for products to transfer"""
    search_term = request.GET.get('search', '').strip()
    autocomplete = request.GET.get('autocomplete') == 'true'
    
    if not search_term:
        return JsonResponse({
            'success': False,
            'message': 'Please enter a product code or SKU'
        }, status=400)
    
    try:
        # Search products (show all, but we'll validate ownership later)
        products = Product.objects.filter(
            Q(product_code__icontains=search_term) |
            Q(name__icontains=search_term) |
            Q(sku_value__iexact=search_term),
            is_active=True
        ).select_related('category', 'owner')
        
        if not products.exists():
            return JsonResponse({
                'success': False,
                'message': f'No products found matching "{search_term}"'
            }, status=404)
        
        # Autocomplete response
        if autocomplete:
            suggestions = []
            for p in products[:10]:
                owner_name = p.owner.username if p.owner else 'FIELDMAX'
                is_mine = p.owner == request.user if p.owner else False
                
                suggestions.append({
                    'id': p.id,
                    'name': p.name,
                    'product_code': p.product_code,
                    'category': p.category.name,
                    'current_quantity': p.quantity or 0,
                    'is_single_item': p.category.is_single_item,
                    'owner': owner_name,
                    'is_mine': is_mine
                })
            return JsonResponse({
                'success': True,
                'suggestions': suggestions
            })
        
        # Multiple products found
        if products.count() > 1:
            product_list = []
            for p in products:
                owner_name = p.owner.username if p.owner else 'FIELDMAX'
                is_mine = p.owner == request.user if p.owner else False
                
                product_list.append({
                    'id': p.id,
                    'name': p.name,
                    'product_code': p.product_code,
                    'sku_value': p.sku_value or 'N/A',
                    'category': p.category.name,
                    'current_quantity': p.quantity or 0,
                    'buying_price': float(p.buying_price or 0),
                    'selling_price': float(p.selling_price or 0),
                    'is_single_item': p.category.is_single_item,
                    'status': p.status,
                    'owner': owner_name,
                    'is_mine': is_mine
                })
            
            return JsonResponse({
                'success': True,
                'multiple': True,
                'products': product_list
            })
        
        # Single product found
        product = products.first()
        
        # Check ownership (admins can transfer any product)
        is_mine = product.owner == request.user if product.owner else False
        is_admin = request.user.is_superuser or request.user.is_staff
        
        if not is_mine and not is_admin:
            return JsonResponse({
                'success': False,
                'message': f'"{product.name}" belongs to {product.owner.username if product.owner else "FIELDMAX"}. You can only transfer your own products.'
            }, status=403)
        
        # Check if product can be transferred
        if product.category.is_single_item and product.status == 'sold':
            return JsonResponse({
                'success': False,
                'message': f'"{product.name}" has already been sold and cannot be transferred'
            }, status=400)
        
        if not product.category.is_single_item and product.quantity == 0:
            return JsonResponse({
                'success': False,
                'message': f'"{product.name}" is out of stock'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'multiple': False,
            'product': {
                'id': product.id,
                'name': product.name,
                'product_code': product.product_code,
                'sku_value': product.sku_value or 'N/A',
                'category': product.category.name,
                'current_quantity': product.quantity or 0,
                'buying_price': float(product.buying_price or 0),
                'selling_price': float(product.selling_price or 0),
                'is_single_item': product.category.is_single_item,
                'status': product.status,
                'owner': product.owner.username if product.owner else 'FIELDMAX',
                'is_mine': is_mine,
                'is_admin': is_admin
            }
        })
    
    except Exception as e:
        logger.error(f"Transfer search error: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Search error: {str(e)}'
        }, status=500)













# ===========================================
# PRODUCT TRANSFER PROCESS
#============================================

@login_required
@require_http_methods(["POST"])
def product_transfer_process(request):
    """Process product transfer - ownership change only"""
    try:
        product_id = request.POST.get('product_id')
        user_id = request.POST.get('user_id')
        quantity = request.POST.get('quantity', 1)
        
        # Validation
        if not all([product_id, user_id]):
            return JsonResponse({
                'success': False,
                'message': 'Product and recipient user are required'
            }, status=400)
        
        try:
            quantity = int(quantity)
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid quantity'
            }, status=400)
        
        if quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Quantity must be greater than 0'
            }, status=400)
        
        # Get product (admins can access any product, regular users only their own)
        if request.user.is_superuser or request.user.is_staff:
            product = get_object_or_404(
                Product.objects.select_related('category', 'owner'),
                pk=product_id,
                is_active=True
            )
        else:
            product = get_object_or_404(
                Product.objects.select_related('category', 'owner'),
                pk=product_id,
                is_active=True,
                owner=request.user
            )
        
        # Get recipient user
        try:
            recipient = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Recipient user not found'
            }, status=404)
        
        # Check if transferring to self
        if recipient.id == request.user.id and product.owner == request.user:
            return JsonResponse({
                'success': False,
                'message': 'Cannot transfer to yourself'
            }, status=400)
        
        # Process transfer
        with transaction.atomic():
            old_owner = product.owner.username if product.owner else "FIELDMAX"
            
            # ========================================
            # SINGLE ITEM TRANSFER
            # ========================================
            if product.category.is_single_item:
                if product.status == 'sold':
                    return JsonResponse({
                        'success': False,
                        'message': 'Product has already been sold'
                    }, status=400)
                
                # For single items, quantity must be 1
                if quantity != 1:
                    return JsonResponse({
                        'success': False,
                        'message': 'Single items can only be transferred one at a time'
                    }, status=400)
                
                # Simply change owner
                product.owner = recipient
                product.save()
                
                logger.info(
                    f"[TRANSFER] Single item {product.product_code} | "
                    f"{old_owner} → {recipient.username} | "
                    f"By: {request.user.username}"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'"{product.name}" successfully transferred to {recipient.username}',
                    'product': {
                        'id': product.id,
                        'name': product.name,
                        'product_code': product.product_code,
                        'new_owner': recipient.username,
                        'previous_owner': old_owner,
                        'quantity': 1
                    }
                })
            
            # ========================================
            # BULK ITEM TRANSFER (Only full transfers allowed)
            # ========================================
            else:
                current_qty = product.quantity or 0
                
                # Validate stock availability
                if current_qty == 0:
                    return JsonResponse({
                        'success': False,
                        'message': 'Product is out of stock'
                    }, status=400)
                
                # Check if it's a FULL transfer
                if quantity != current_qty:
                    return JsonResponse({
                        'success': False,
                        'message': f'‼️‼️‼️ NOT ALLOWED. '
                                   f'Kinly contact store manager for asistance.'
                    }, status=400)
                
                # Process FULL transfer
                product.owner = recipient
                product.save()
                
                # Create stock audit entry for full transfer
                buying_price = product.buying_price or Decimal('0.00')
                StockEntry.objects.create(
                    product=product,
                    quantity=-current_qty,  # Stock OUT from old owner
                    entry_type='transfer_out',
                    unit_price=buying_price,
                    total_amount=current_qty * buying_price,
                    created_by=request.user,
                    notes=f"Full transfer: {old_owner} → {recipient.username}"
                )
                
                logger.info(
                    f"[TRANSFER] Full bulk transfer {product.product_code} | "
                    f"{quantity} units | {old_owner} → {recipient.username} | "
                    f"By: {request.user.username}"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'All {quantity} unit(s) of "{product.name}" transferred to {recipient.username}',
                    'product': {
                        'id': product.id,
                        'name': product.name,
                        'product_code': product.product_code,
                        'quantity_transferred': quantity,
                        'remaining_quantity': 0,
                        'previous_owner': old_owner,
                        'new_owner': recipient.username
                    }
                })
    
    except Product.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Product not found or not owned by you'
        }, status=404)
    
    except Exception as e:
        logger.error(f"Transfer error: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'message': f'Transfer failed: {str(e)}'
        }, status=500)











# ===========================================
# INVENTORY PRODUCT LOOKUP VIEW
#============================================

class InventoryProductLookupView(LoginRequiredMixin, View):
    """
    Search for products by product_code or SKU value
    Used in POS/Sales systems
    """
    
    def get(self, request):
        search_term = request.GET.get("product_code", "").strip()
        
        if not search_term:
            return JsonResponse({
                "status": "error",
                "message": "Search term is required"
            })
        
        # Search by product_code or sku_value
        product = Product.objects.filter(
            Q(product_code__iexact=search_term) | Q(sku_value__iexact=search_term),
            is_active=True
        ).select_related('category').first()
        
        if not product:
            return JsonResponse({
                "status": "error",
                "message": "Product not found"
            })
        
        # Check if product is available
        if product.status in ['sold', 'outofstock']:
            return JsonResponse({
                "status": "error",
                "message": f"Product is {product.get_status_display()}"
            })
        
        return JsonResponse({
            "status": "success",
            "product_id": product.id,
            "product_name": product.name,
            "product_code": product.product_code,
            "sku_value": product.sku_value or "N/A",
            "sku_value": product.sku_value,
            "quantity": product.quantity or 0,
            "selling_price": str(product.selling_price or '0.00'),
            "buying_price": str(product.buying_price or '0.00'),
            "category": product.category.name,
            "item_type": product.category.item_type,
            "is_single_item": product.category.is_single_item,
            "category_code": product.category.category_code, 
            "created_at": product.created_at.isoformat(),
        })










# ====================================
# STOCK ENTRY LIST VIEWS
# ====================================

class StockEntryListView(LoginRequiredMixin, ListView):
    model = StockEntry
    template_name = "inventory/stockentry_list.html"
    context_object_name = "entries"
    paginate_by = 50
    
    def get_queryset(self):
        queryset = StockEntry.objects.select_related(
            'product', 'product__category', 'created_by'
        ).all()
        
        # Filter by product
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        # Filter by entry type
        entry_type = self.request.GET.get('entry_type')
        if entry_type:
            queryset = queryset.filter(entry_type=entry_type)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(is_active=True)
        context['entry_types'] = StockEntry.ENTRY_TYPE_CHOICES
        return context















# ===========================================
# STOCK ENTRY CREATE VIEW
#============================================

class StockEntryCreateView(LoginRequiredMixin, CreateView):
    model = StockEntry
    form_class = StockEntryForm
    template_name = "inventory/stockentry_form.html"
    success_url = reverse_lazy("stockentry-list")
    
    def form_valid(self, form):
        try:
            # Set created_by
            form.instance.created_by = self.request.user
            
            response = super().form_valid(form)
            
            # AJAX response
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': 'Stock entry created successfully',
                    'entry_id': self.object.pk
                })
            
            return response
            
        except Exception as e:
            print("Error creating stock entry:")
            print(traceback.format_exc())
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f'Error: {str(e)}'
                }, status=400)
            raise














# ====================================
# GET PRODUCT BY SKU
# ====================================

@login_required
def get_product_by_sku(request):
    """Get product info by SKU value (for barcode scanning)"""
    sku_value = request.GET.get('sku', '').strip()
    
    if not sku_value:
        return JsonResponse({'status': 'error', 'message': 'SKU required'})
    
    product = Product.objects.filter(
        sku_value=sku_value,
        is_active=True
    ).select_related('category').first()
    
    if not product:
        return JsonResponse({'status': 'error', 'message': 'Product not found'})
    
    return JsonResponse({
        'status': 'success',
        'product': {
            'id': product.id,
            'name': product.name,
            'product_code': product.product_code,
            'sku_value': product.sku_value,
            'quantity': product.quantity or 0,
            'selling_price': float(product.selling_price or 0),
            'status': product.status,
        }
    })












# ===========================================
# DASHBOARD STATS
#============================================

@login_required
def dashboard_stats(request):
    """Get inventory statistics for dashboard"""
    
    total_products = Product.objects.filter(is_active=True).count()
    
    # Single items stats
    single_items = Product.objects.filter(
        is_active=True,
        category__item_type='single'
    )
    single_available = single_items.filter(status='available').count()
    single_sold = single_items.filter(status='sold').count()
    
    # Bulk items stats
    bulk_items = Product.objects.filter(
        is_active=True,
        category__item_type='bulk'
    )
    bulk_available = bulk_items.filter(status='available').count()
    bulk_lowstock = bulk_items.filter(status='lowstock').count()
    bulk_outofstock = bulk_items.filter(status='outofstock').count()
    
    # Inventory value - calculate safely
    total_value = Decimal('0.00')
    for p in Product.objects.filter(is_active=True):
        buying_price = p.buying_price or Decimal('0.00')
        quantity = p.quantity or 0
        total_value += buying_price * quantity
    
    return JsonResponse({
        'total_products': total_products,
        'single_items': {
            'total': single_items.count(),
            'available': single_available,
            'sold': single_sold,
        },
        'bulk_items': {
            'total': bulk_items.count(),
            'available': bulk_available,
            'lowstock': bulk_lowstock,
            'outofstock': bulk_outofstock,
        },
        'inventory_value': float(total_value),
    })
















# ===============================
# PRODUCT LIST
# ===============================

def product_list(request):
    # Get filters from the request (GET params)
    status_filter = request.GET.get('status', 'all')
    category_filter = request.GET.get('category', 'all')
    type_filter = request.GET.get('type', 'all')

    products = Product.objects.select_related('category', 'owner').all()

    # ---------- FILTERING ----------
    # Filter by category
    if category_filter != 'all':
        products = products.filter(category_id=category_filter)

    # Filter by type (single / bulk)
    if type_filter == 'single':
        products = products.filter(category__is_single_item=True)
    elif type_filter == 'bulk':
        products = products.filter(category__is_single_item=False)

    # Filter by stock status
    if status_filter != 'all':
        if status_filter == 'instock':
            products = products.filter(quantity__gt=0)
        elif status_filter == 'outofstock':
            products = products.filter(quantity=0)
        elif status_filter == 'lowstock':
            products = products.filter(quantity__lte=5, quantity__gt=0)

    # ---------- CALCULATIONS ----------
    products_with_margin_and_status = []
    for p in products:
        # margin calculation
        if p.buying_price and p.buying_price > 0:
            margin_pct = ((p.selling_price - p.buying_price) / p.buying_price) * 100
        else:
            margin_pct = 0

        # status logic
        if p.category.is_single_item:
            status = 'outofstock' if p.status == 'sold' else 'instock'
        else:
            if p.quantity == 0:
                status = 'outofstock'
            elif p.quantity <= 5:
                status = 'lowstock'
            else:
                status = 'instock'

        products_with_margin_and_status.append({
            'product': p,
            'margin_pct': margin_pct,
            'status': status
        })

    # ---------- COUNTS ----------
    total_products = Product.objects.count()

    in_stock_count = Product.objects.filter(quantity__gt=0).count()
    low_stock_count = Product.objects.filter(quantity__lte=5, quantity__gt=0).count()
    out_of_stock_count = Product.objects.filter(quantity=0).count()

    categories = Category.objects.all()

    context = {
        'products_with_margin_and_status': products_with_margin_and_status,
        'total_products': total_products,
        'in_stock_count': in_stock_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'categories': categories
    }

    return render(request, 'website/products.html', context)


