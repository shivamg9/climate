import React from 'react';
import { Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  BarElement,
  Filler,
} from 'chart.js';

// Register required chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  BarElement,
  Filler
);

export const HazardAnalysisChart = ({ data }) => {
  if (!data) return null;

  const years = data.series.map(item => item.year);
  const heatwaveDays = data.series.map(item => item.heatwave_days);
  const events = data.series.map(item => item.events);
  const rollingAvg = data.series.map(item => item.rolling_avg || null);
  const maxDuration = data.series.map(item => item.max_duration);
  const meanIntensity = data.series.map(item => item.mean_intensity);

  // Compute regression trendline for heatwave days
  // trend.slope_per_decade is slope per decade, convert to per year
  const slopePerYear = (data.trend?.slope_per_decade || 0) / 10;
  // Use the mean year and mean heatwave days as reference point for the line
  const meanYear = years.reduce((a, b) => a + b, 0) / years.length;
  const meanHeatwaveDays = heatwaveDays.reduce((a, b) => a + b, 0) / heatwaveDays.length;
  // intercept = mean_y - slope * mean_x
  const intercept = meanHeatwaveDays - slopePerYear * meanYear;
  const trendlineData = years.map(year => intercept + slopePerYear * year);

  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      title: {
        display: true,
        text: 'Heatwave Analysis Results'
      },
      tooltip: {
        mode: 'index',
        intersect: false,
      }
    },
    scales: {
      y: {
        beginAtZero: true
      }
    }
  };

  return (
    <div className="chart-container">
      <div className="chart-grid">
        <div className="chart-item">
          <Bar
            data={{
              labels: years,
              datasets: [
                {
                  label: 'Heatwave Days per Year',
                  data: heatwaveDays,
                  backgroundColor: 'rgba(255, 99, 132, 0.6)',
                  borderColor: 'rgba(255, 99, 132, 1)',
                  borderWidth: 1
                },
                {
                  label: '5-Year Rolling Average',
                  data: rollingAvg,
                  type: 'line',
                  borderColor: 'rgba(54, 162, 235, 1)',
                  backgroundColor: 'rgba(54, 162, 235, 0.2)',
                  borderWidth: 2,
                  tension: 0.3,
                  pointRadius: 0
                },
                {
                  label: 'Trend (Linear Regression)',
                  data: trendlineData,
                  type: 'line',
                  borderColor: 'rgba(255, 206, 86, 1)',
                  borderWidth: 2,
                  borderDash: [5, 5],
                  fill: false,
                  pointRadius: 0,
                  tension: 0
                }
              ]
            }}
            options={chartOptions}
          />
        </div>

        <div className="chart-item">
          <Line
            data={{
              labels: years,
              datasets: [
                {
                  label: 'Heatwave Events per Year',
                  data: events,
                  borderColor: 'rgba(255, 159, 64, 1)',
                  backgroundColor: 'rgba(255, 159, 64, 0.2)',
                  tension: 0.3
                },
                {
                  label: 'Max Duration (days)',
                  data: maxDuration,
                  borderColor: 'rgba(75, 192, 192, 1)',
                  backgroundColor: 'rgba(75, 192, 192, 0.2)',
                  tension: 0.3,
                  yAxisID: 'y1'
                }
              ]
            }}
            options={{
              ...chartOptions,
              scales: {
                y: {
                  beginAtZero: true,
                  position: 'left',
                },
                y1: {
                  beginAtZero: true,
                  position: 'right',
                  grid: {
                    drawOnChartArea: false,
                  }
                }
              }
            }}
          />
        </div>
      </div>

      <div className="chart-item full-width">
        <Line
          data={{
            labels: years,
            datasets: [
              {
                label: 'Mean Intensity (°C exceedance)',
                data: meanIntensity,
                borderColor: 'rgba(153, 102, 255, 1)',
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                tension: 0.3
              }
            ]
          }}
          options={chartOptions}
        />
      </div>
    </div>
  );
};