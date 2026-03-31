import React, { useState, useEffect } from 'react';
import { awsAPI } from '../services/api';
import './ResourcesPage.css';

export default function ResourcesPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('ec2');

  useEffect(() => {
    awsAPI.getResources()
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-spinner"><div className="spinner"></div></div>;

  if (!data) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <h2>No resource data</h2>
        <p style={{ color: 'var(--gray-500)' }}>Connect your AWS account first.</p>
      </div>
    );
  }

  const tabs = [
    { key: 'ec2', label: 'EC2 Instances', count: data.ec2_instances?.length || 0, icon: '🖥️' },
    { key: 'ebs', label: 'EBS Volumes', count: data.ebs_volumes?.length || 0, icon: '💾' },
    { key: 's3', label: 'S3 Buckets', count: data.s3_buckets?.length || 0, icon: '🪣' },
    { key: 'rds', label: 'RDS Instances', count: data.rds_instances?.length || 0, icon: '🗄️' },
    { key: 'eip', label: 'Elastic IPs', count: data.elastic_ips?.length || 0, icon: '🌐' },
  ];

  return (
    <div className="resources-page">
      <div className="page-header">
        <h1>🖥️ AWS Resources</h1>
        <p>Region: {data.region}</p>
      </div>

      {/* Resource Summary */}
      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        {tabs.map(tab => (
          <div
            key={tab.key}
            className={`kpi-card mini clickable ${activeTab === tab.key ? 'active-tab' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <div style={{ fontSize: 24, marginBottom: 4 }}>{tab.icon}</div>
            <div className="kpi-value">{tab.count}</div>
            <div className="kpi-label">{tab.label}</div>
          </div>
        ))}
      </div>

      {/* EC2 Instances Table */}
      {activeTab === 'ec2' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">EC2 Instances ({data.ec2_instances?.length || 0})</div>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Instance ID</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>AZ</th>
                  <th>Public IP</th>
                </tr>
              </thead>
              <tbody>
                {(data.ec2_instances || []).map((inst, i) => (
                  <tr key={i}>
                    <td><code>{inst.instance_id}</code></td>
                    <td>{inst.name || '—'}</td>
                    <td>{inst.instance_type}</td>
                    <td>
                      <span className={`badge ${inst.state === 'running' ? 'badge-success' : 'badge-medium'}`}>
                        {inst.state}
                      </span>
                    </td>
                    <td>{inst.availability_zone}</td>
                    <td>{inst.public_ip || '—'}</td>
                  </tr>
                ))}
                {(!data.ec2_instances || data.ec2_instances.length === 0) && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', color: 'var(--gray-400)' }}>No EC2 instances found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* EBS Volumes Table */}
      {activeTab === 'ebs' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">EBS Volumes ({data.ebs_volumes?.length || 0})</div>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Volume ID</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>State</th>
                  <th>Attached To</th>
                </tr>
              </thead>
              <tbody>
                {(data.ebs_volumes || []).map((vol, i) => (
                  <tr key={i}>
                    <td><code>{vol.volume_id}</code></td>
                    <td>{vol.name || '—'}</td>
                    <td>{vol.volume_type}</td>
                    <td>{vol.size_gb} GB</td>
                    <td>
                      <span className={`badge ${vol.state === 'in-use' ? 'badge-success' : 'badge-medium'}`}>
                        {vol.state}
                      </span>
                    </td>
                    <td>{vol.attached_to || '—'}</td>
                  </tr>
                ))}
                {(!data.ebs_volumes || data.ebs_volumes.length === 0) && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', color: 'var(--gray-400)' }}>No EBS volumes found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* S3 Buckets Table */}
      {activeTab === 's3' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">S3 Buckets ({data.s3_buckets?.length || 0})</div>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Bucket Name</th>
                  <th>Region</th>
                  <th>Size</th>
                  <th>Objects</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {(data.s3_buckets || []).map((b, i) => (
                  <tr key={i}>
                    <td><code>{b.bucket_name}</code></td>
                    <td>{b.region}</td>
                    <td>{b.size_gb} GB</td>
                    <td>{b.object_count}</td>
                    <td>{b.creation_date ? new Date(b.creation_date).toLocaleDateString() : '—'}</td>
                  </tr>
                ))}
                {(!data.s3_buckets || data.s3_buckets.length === 0) && (
                  <tr><td colSpan="5" style={{ textAlign: 'center', color: 'var(--gray-400)' }}>No S3 buckets found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* RDS Instances Table */}
      {activeTab === 'rds' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">RDS Instances ({data.rds_instances?.length || 0})</div>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Instance ID</th>
                  <th>Engine</th>
                  <th>Class</th>
                  <th>Storage</th>
                  <th>Status</th>
                  <th>Multi-AZ</th>
                </tr>
              </thead>
              <tbody>
                {(data.rds_instances || []).map((db, i) => (
                  <tr key={i}>
                    <td><code>{db.db_instance_id}</code></td>
                    <td>{db.engine} {db.engine_version}</td>
                    <td>{db.db_instance_class}</td>
                    <td>{db.storage_gb} GB</td>
                    <td>
                      <span className={`badge ${db.status === 'available' ? 'badge-success' : 'badge-medium'}`}>
                        {db.status}
                      </span>
                    </td>
                    <td>{db.multi_az ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
                {(!data.rds_instances || data.rds_instances.length === 0) && (
                  <tr><td colSpan="6" style={{ textAlign: 'center', color: 'var(--gray-400)' }}>No RDS instances found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Elastic IPs Table */}
      {activeTab === 'eip' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Elastic IPs ({data.elastic_ips?.length || 0})</div>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Public IP</th>
                  <th>Allocation ID</th>
                  <th>Instance</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(data.elastic_ips || []).map((eip, i) => (
                  <tr key={i}>
                    <td><code>{eip.public_ip}</code></td>
                    <td>{eip.allocation_id}</td>
                    <td>{eip.instance_id || '—'}</td>
                    <td>
                      <span className={`badge ${eip.is_associated ? 'badge-success' : 'badge-medium'}`}>
                        {eip.is_associated ? 'Associated' : 'Unassociated'}
                      </span>
                    </td>
                  </tr>
                ))}
                {(!data.elastic_ips || data.elastic_ips.length === 0) && (
                  <tr><td colSpan="4" style={{ textAlign: 'center', color: 'var(--gray-400)' }}>No Elastic IPs found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
