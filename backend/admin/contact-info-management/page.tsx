'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Trash2, Edit, Plus, Save, X } from 'lucide-react';
import { toast } from 'sonner';

interface ContactInfo {
  id: number;
  category: string;
  label: string;
  value: string;
  is_active: boolean;
  is_primary: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
}

interface ContactInfoCreate {
  category: string;
  label: string;
  value: string;
  is_active: boolean;
  is_primary: boolean;
  display_order: number;
}

const CATEGORIES = [
  'phone',
  'email',
  'address',
  'social',
  'website',
  'other'
];

export default function ContactInfoManagement() {
  const [contactInfos, setContactInfos] = useState<ContactInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<ContactInfoCreate>({
    category: 'phone',
    label: '',
    value: '',
    is_active: true,
    is_primary: false,
    display_order: 0
  });

  useEffect(() => {
    fetchContactInfos();
  }, []);

  const fetchContactInfos = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v1/admin/contact-info', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setContactInfos(data.items || []);
      } else {
        toast.error('Failed to fetch contact information');
      }
    } catch (error) {
      console.error('Error fetching contact infos:', error);
      toast.error('Error fetching contact information');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const token = localStorage.getItem('token');
      const url = editingId 
        ? `/api/v1/admin/contact-info/${editingId}`
        : '/api/v1/admin/contact-info';
      
      const method = editingId ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });
      
      if (response.ok) {
        toast.success(editingId ? 'Contact info updated successfully' : 'Contact info created successfully');
        fetchContactInfos();
        resetForm();
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Operation failed');
      }
    } catch (error) {
      console.error('Error saving contact info:', error);
      toast.error('Error saving contact information');
    }
  };

  const handleEdit = (contactInfo: ContactInfo) => {
    setFormData({
      category: contactInfo.category,
      label: contactInfo.label,
      value: contactInfo.value,
      is_active: contactInfo.is_active,
      is_primary: contactInfo.is_primary,
      display_order: contactInfo.display_order
    });
    setEditingId(contactInfo.id);
    setShowAddForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this contact information?')) {
      return;
    }
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/v1/admin/contact-info/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        toast.success('Contact info deleted successfully');
        fetchContactInfos();
      } else {
        toast.error('Failed to delete contact info');
      }
    } catch (error) {
      console.error('Error deleting contact info:', error);
      toast.error('Error deleting contact information');
    }
  };

  const resetForm = () => {
    setFormData({
      category: 'phone',
      label: '',
      value: '',
      is_active: true,
      is_primary: false,
      display_order: 0
    });
    setEditingId(null);
    setShowAddForm(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">Loading contact information...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Contact Information Management</h1>
          <p className="text-muted-foreground">
            Manage company contact details displayed on the website
          </p>
        </div>
        <Button onClick={() => setShowAddForm(true)} className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Add Contact Info
        </Button>
      </div>

      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? 'Edit Contact Information' : 'Add New Contact Information'}</CardTitle>
            <CardDescription>
              {editingId ? 'Update the contact information details' : 'Create a new contact information entry'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="category">Category</Label>
                  <Select
                    value={formData.category}
                    onValueChange={(value) => setFormData({ ...formData, category: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((category) => (
                        <SelectItem key={category} value={category}>
                          {category.charAt(0).toUpperCase() + category.slice(1)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="label">Label</Label>
                  <Input
                    id="label"
                    value={formData.label}
                    onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                    placeholder="e.g., Main Office, Support Email"
                    required
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="value">Value</Label>
                <Textarea
                  id="value"
                  value={formData.value}
                  onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                  placeholder="Contact information value"
                  required
                />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="display_order">Display Order</Label>
                  <Input
                    id="display_order"
                    type="number"
                    value={formData.display_order}
                    onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) || 0 })}
                    min="0"
                  />
                </div>
                
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded"
                  />
                  <Label htmlFor="is_active">Active</Label>
                </div>
                
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_primary"
                    checked={formData.is_primary}
                    onChange={(e) => setFormData({ ...formData, is_primary: e.target.checked })}
                    className="rounded"
                  />
                  <Label htmlFor="is_primary">Primary</Label>
                </div>
              </div>
              
              <div className="flex gap-2">
                <Button type="submit" className="flex items-center gap-2">
                  <Save className="h-4 w-4" />
                  {editingId ? 'Update' : 'Create'}
                </Button>
                <Button type="button" variant="outline" onClick={resetForm} className="flex items-center gap-2">
                  <X className="h-4 w-4" />
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {contactInfos.length === 0 ? (
          <Card>
            <CardContent className="flex items-center justify-center h-32">
              <p className="text-muted-foreground">No contact information found. Add some to get started.</p>
            </CardContent>
          </Card>
        ) : (
          contactInfos.map((contactInfo) => (
            <Card key={contactInfo.id}>
              <CardContent className="p-6">
                <div className="flex justify-between items-start">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {contactInfo.category.charAt(0).toUpperCase() + contactInfo.category.slice(1)}
                      </Badge>
                      <h3 className="font-semibold">{contactInfo.label}</h3>
                      {contactInfo.is_primary && (
                        <Badge variant="default">Primary</Badge>
                      )}
                      {!contactInfo.is_active && (
                        <Badge variant="destructive">Inactive</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">{contactInfo.value}</p>
                    <p className="text-xs text-muted-foreground">
                      Order: {contactInfo.display_order} | Created: {new Date(contactInfo.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleEdit(contactInfo)}
                      className="flex items-center gap-1"
                    >
                      <Edit className="h-3 w-3" />
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(contactInfo.id)}
                      className="flex items-center gap-1"
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}